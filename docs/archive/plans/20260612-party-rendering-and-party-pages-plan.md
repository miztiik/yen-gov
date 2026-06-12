# Party rendering + per-party pages (rip-and-replace)

**Last Updated**: 2026-06-12

**Status**: DESIGN-LOCKED — 5-PR rip-and-replace, ready to execute.
**Slug shape**: lowercased `party_id` tail with `_` -> `-`; sentinel exceptions noted in section 3.
**URL grammar amendment**: ADR-0053 (this plan) adds top-level `/parties` to RESERVED + extends 5-way disjointness to 6-way.
**Closed-renderer extension**: `DualAxisBarLine.svelte` ADR inline-folded into PR-4.
**Doctrine route**: `link.party(party_id)` is the SINGLE party-page link builder; PartyPill is the SINGLE party-rendering primitive.

## 0. Why this exists

User direction 2026-06-12: "B + C. For C follow indiavotes model. /parties for all parties list. Per-party page like https://www.indiavotes.com/parties/inc/ (graphs only — seats over years + vote share + strongholds, no big election-by-election table). Clicking PartyPill should lead to the party page. Show symbol if it is there, if not REMOVE the symbol (no placeholder). Show wiki link, founded, party metadata with glyphs (Jony jazz it up). Tooltip example: screenshot showing card with symbol + short + full + Chief + Founded. Work with Hans + Fowler on URL grammar — some parties regional, some national, can't shove under /state. No strangler-fig nonsense, just rip-and-replace — temporarily breaking things is acceptable."

This plan delivers:

- **Standardise**: every citizen-facing party reference renders via `<PartyPill>` and links to `/parties/<slug>`.
- **Tooltip**: hover/focus/click-pin popover with symbol + short + full + founded + recognition (no "Chief" — no column exists, per Max's verdict).
- **/parties index**: alphabetical list + recognition-scope filter chips + search.
- **/parties/&lt;slug&gt; detail**: indiavotes-style — header with party-coloured avatar, KPI strip, LS bar+line, VS bar+line, top-10 strongholds, metadata footer.
- **Rip-and-replace**: delete the old `/:state/party/<slug>` route, delete the old `Party.svelte`, delete `partyInState()` + `link.party(state, eci, short)` overload, delete `partySlug()` helper. Atomic in PR-0.

## 1. Persona verdicts (binding, do NOT re-litigate)

Verdicts solicited 2026-06-12. Each citation links to the verdict body that authorises the call.

| Decision | Verdict | Authority |
|---|---|---|
| Per-party page identity | Party-scoped: `/parties/<slug>` is canonical. State view is a SECTION inside the page, not a path. | Hans (governance) |
| Old `/:state/party/<slug>` route | DELETE (no citizen redirect; PR-P4 precedent). | Fowler verdict 1; user "rip-and-replace" 2026-06-12 |
| Slug shape | Lowercased `party_id` tail with `_` -> `-`. Unique by construction (verified: 2259/2259 unique tails on parties.csv). Sentinel exceptions: `parties.IN.IND` -> `/parties/independent` (Hans: spelled-out citizen framing), `parties.IN.NOTA` -> `/parties/nota`, `parties.IN.UNK` -> no page (resolver fallback, not a citizen entity). | Fowler verdict 2 + Hans verdict 5 |
| National vs state-only URL discrimination | Flat: `/parties/<slug>` for everyone. `recognition_scope` lives in page chrome only. AAP's 2024 reclassification doesn't break URLs. | Hans verdict 4 |
| Reserve `parties` (plural) | YES, top-level token. 6-way disjointness in url-namespace-disjointness.test.ts. | Hans verdict 6 + Fowler verdict 5 |
| Migration topology | RIP-AND-REPLACE per user 2026-06-12. PR-0 deletes old route + Party.svelte + link.party overload IN THE SAME COMMIT as it adds the new shape. No STUB phase, no strangler-fig, no redirect. (Override of Fowler verdict 1's 3-PR shape; Fowler verdict 1's substance — "no citizen-facing redirect, just delete" — survives.) | User 2026-06-12 |
| /parties index data | DuckDB-WASM read parties.csv directly. No precompute. | Fowler verdict 4 |
| Tooltip style | Keep existing 4-tier PartyPill (anchor/brand/fallback/neutral). Add hover+focus+click-pin popover. Hand-roll like `ChartTooltip.svelte`. No `@floating-ui` dep. | Jony A1 + A4 |
| Tooltip fields | symbol (if present) + short + full + founded_year + dissolved_year (only if non-null) + recognition_scope + name_native_script + wiki external-link icon at bottom-right. NO "Chief" (column doesn't exist; don't fabricate). | Jony A2 + Max section 3 |
| Missing symbol rule | Render nothing. Left-align short. NO placeholder, NO initials avatar, NO coloured circle. (User's literal instruction.) | Jony A3 |
| Page section order | (1) Header with party-coloured avatar + name + sub-line. (2) Latest-of one-liner per body (LS + VS separately). (3) KPI 2x2 (LS seats, VS seats, elections contested, active range). (4) LS DualAxisBarLine chart. (5) VS DualAxisBarLine chart. (6) Strongholds top-10 per body (list + tiny W/L sparkline). (7) Metadata footer with Lucide glyphs. | Jony B1 + B7 |
| Chart primitive | NEW `DualAxisBarLine.svelte` under `frontend/src/lib/charts/`. ADR-0053 (this plan) folds in the closed-renderer extension per [docs/concepts/schema-is-the-design-system.md](../docs/concepts/schema-is-the-design-system.md). | Jony B2 |
| Strongholds | Top-10 list per body + tiny W/L sparkline. NOT a choropleth (deferred). | Jony B3 |
| Header card | 80px coloured square (full-bleed for anchor; ring for brand/fallback; grey for sentinel) + party short in bold + name to the right. Uses `getPartyColor(party_id, row)`. | Jony B5 |
| Mobile chart | Thin X-axis labels (every 4th election) at <640px; tap-to-detail; no horizontal scroll. | Jony B6 |

## 2. Out of scope (deferred to separate PRs)

These were named in persona verdicts but explicitly deferred to avoid blowing the budget:

- **"Chief / President" column on parties.csv.** No column exists. Adding it is a Wikidata P488 ingest (Max section 3). Defer; tooltip drops the line.
- **`/parties/nota` + `/parties/independent` page bodies.** These ARE in scope as routes (they reach the same Party.svelte body). The Hans-mandated extra framing (NOTA legal-context caveat per *PUCL v. Union of India 2013*; Independent aggregate-not-entity framing) is a follow-up PR — the v1 page renders the same KPI + chart shape and is honest (NOTA has no recognition_scope, no symbol, no wiki; KPIs still meaningful).
- **Pre-1999 LS history backfill.** Max section 4: yen-gov has LS 1999-2024 only; 1952-1998 needs a TCPD LS Panel ingest re-run. v1 page surfaces only what's in the canonical store; a coverage caption ("Pre-1999 LS history not yet ingested") goes under each chart. Backfill is a separate Hans+Max-blessed ingest PR.
- **Constituency-level "strongholds" choropleth.** Jony B3 deferred. v1 ships the top-10 list + sparkline.
- **Wikidata-sourced metadata enrichment** (chief, founded_year for BSP/CPIM, symbol for NCP/LJP). Hand-curate two `founded_year` + two `symbol_asset` cells in a tiny one-row CSV-edit PR after PR-4 lands.
- **AAP / SHS_UBT / NCP_SP recognition-flip annotation strip on the chart.** OWID-style methodology-break overlay — Hans-territory follow-up.
- **`ADK` (TCPD short for old AIADMK) -> `AIADMK` resolver tail.** Per Max section 6: pre-2008 AIADMK strongholds undercounted. Track in the next eci_ae_panel re-run.

## 3. URL grammar amendment (PR-0)

Adds rows to [docs/architecture/frontend/url-grammar.md](../docs/architecture/frontend/url-grammar.md) "Final route grammar" table:

| Surface | URL | Component | Crumbs |
|---|---|---|---|
| Parties index | `/parties` | `PartiesIndex.svelte` | Home -> Parties |
| Per-party detail | `/parties/<slug>` | `Party.svelte` (rebuilt) | Home -> Parties -> &lt;short&gt; |

Removes: `Party-in-state` row (`/<state>/party/<slug>`).

`RESERVED_PATH_TOKENS` additions in [frontend/src/lib/links.ts](../frontend/src/lib/links.ts): add `"parties"` (plural). Remove: `"party"` (singular) — the legacy sub-namespace marker retires with the route. (Both `party` + `parties` survive together for ZERO PRs — PR-0 swaps them atomically.)

Disjointness contract in [frontend/src/contracts/url-namespace-disjointness.test.ts](../frontend/src/contracts/url-namespace-disjointness.test.ts): extend from 5-way to 6-way by adding `loadPartySlugs(): string[]` (reads parties.csv, maps party_id tail per the slug-shape rule + applies sentinel exceptions, returns deduped list). Assert pairwise disjoint vs `{stateSlugs, topicSlugs, acSlugsAcrossAllStates, urlIndicatorSlugs, RESERVED}`. Internal-uniqueness assertion: `partySlugs.length === new Set(partySlugs).size`.

Slug derivation rule (lock in `frontend/src/lib/slug.ts`):

```typescript
const SENTINEL_SLUG_OVERRIDES = new Map<string, string>([
  ["parties.IN.IND", "independent"], // Hans verdict 5: spelled-out
]);
const NO_PAGE = new Set<string>(["parties.IN.UNK"]); // resolver fallback, no citizen page

export function partyIdToSlug(party_id: string): string | null {
  if (NO_PAGE.has(party_id)) return null;
  if (SENTINEL_SLUG_OVERRIDES.has(party_id)) return SENTINEL_SLUG_OVERRIDES.get(party_id)!;
  // Lowercased party_id tail, _ -> -
  const tail = party_id.split(".").pop() ?? party_id;
  return tail.toLowerCase().replace(/_/g, "-");
}

export function partyIdFromSlug(slug: string): string {
  // Reverse for router: independent -> parties.IN.IND; nota -> parties.IN.NOTA; bjp -> parties.IN.BJP
  for (const [pid, s] of SENTINEL_SLUG_OVERRIDES) if (s === slug) return pid;
  return `parties.IN.${slug.toUpperCase().replace(/-/g, "_")}`;
}
```

The reverse function is used by Party.svelte to resolve `params.slug` -> `party_id`, then it loads parties.csv row by PK. Round-trip test in `links.test.ts`: `partyIdFromSlug(partyIdToSlug(pid)) === pid` for every row in parties.csv except `parties.IN.UNK`.

The `parties.IN.AC` row (`Arunachal Congress`) becomes `/parties/ac`. This is fine: `RESERVED_PATH_TOKENS` applies at position 1 only (state slot); at position 2 inside `/parties/<slot>` the AC slug doesn't conflict with the chrome `ac` reservation.

## 4. PR topology — 5 PRs, 2 waves

```
PR-0 (orchestrator, sub-worktree)
  |
  +--- Wave 1 PARALLEL (file-disjoint)
  |     PR-1 (PartyPill tooltip + meta loader)        -- touches PartyPill + new files
  |     PR-2 (Adopt PartyPill across 5 surfaces)      -- touches consumer .svelte files only
  |
  +--- Wave 2 PARALLEL (file-disjoint)
        PR-3 (PartiesIndex.svelte body + index view-model)
        PR-4 (Party.svelte body + DualAxisBarLine + ADR-0053 inline + party-detail view-model)
```

PR-1 + PR-2 are file-disjoint: PR-1 only touches `frontend/src/lib/party-pill/**` + new loader + tests; PR-2 only touches consumer routes/components and never modifies PartyPill itself.

PR-3 + PR-4 are file-disjoint: PR-3 only touches `PartiesIndex.svelte` + `frontend/src/lib/view-models/parties.ts` (new) + its test; PR-4 only touches `Party.svelte` + new `loadPartyDetail` + new `DualAxisBarLine.svelte` + ADR doc edits. Neither touches `main.ts` (PR-0 wired both routes).

After PR-0 lands the app temporarily renders STUB pages at `/parties` + `/parties/<slug>` ("Coming soon") and may break the 2 callsites visually for ~1 commit cycle (the per-party links now resolve to the stub). Per user: "temporarily breaking things is acceptable." Wave 1 + Wave 2 close the loop.

## 5. PR briefs (executable; each PR is its own atomic ship)

Every brief assumes a fresh sub-worktree off `origin/main`, branch named `feat/parties-pr-N-<slug>`, run gates: backend pytest (with the 3 standing DuckDB-Windows-Py3.14 deselects), frontend vitest, svelte-check, browser smoke on listed routes. Use `bun install --frozen-lockfile` after worktree-add. Subagent returns a single message with branch + PR # + merge SHA + gate results + file-touch count + deviations.

### PR-0 (orchestrator authors directly; ships first)

**Branch**: `feat/parties-pr0-doctrine-and-rip`. **Worktree**: `../yen-gov-parties-pr0`.

**Files touched (atomic; rip-and-replace shape per user direction)**:

1. `frontend/src/lib/slug.ts` — add `partyIdToSlug`, `partyIdFromSlug`, `SENTINEL_SLUG_OVERRIDES`, `NO_PAGE`. DELETE existing `partySlug()` function.
2. `frontend/src/lib/links.ts` — DELETE `partyInState()` builder + existing `party(state, eci, short)` overload + `buildPartySlug` import. ADD new `party(party_id): string | null` (returns `null` when slug derivation returns null, i.e. UNK). ADD new `parties(): string` for the index. Update `RESERVED_PATH_TOKENS`: remove `"party"`, add `"parties"`.
3. `frontend/src/main.ts` — DELETE the `{pattern: "/:state/party/:party", component: Party, ...}` route entry + comments referencing it. ADD `{pattern: "/parties", component: PartiesIndex, ...}` + `{pattern: "/parties/:slug", component: Party, ...}` route entries. UPDATE `Party` import to point at the new (rebuilt) `Party.svelte`. ADD `PartiesIndex` import. ADD `partiesIndexCrumbs` + `partyCrumbs` (updated; was state-scoped) crumb builders.
4. `frontend/src/routes/Party.svelte` — DELETE existing body. REPLACE with STUB: breadcrumb (Home > Parties > &lt;short or slug&gt;) + H1 + "Coming soon (PR-4 builds the body)" + visible `data-testid="party-page-stub"`. Resolves slug -> party_id -> parties.csv row via the new `loadPartyMeta(party_id)` (PR-1 ships the full loader; STUB version inline-derives short from slug).
5. `frontend/src/routes/PartiesIndex.svelte` — NEW STUB. Breadcrumb (Home > Parties) + H1 + "Coming soon (PR-3 builds the index)" + visible `data-testid="parties-index-stub"`.
6. `frontend/src/routes/StateOverview.svelte` line 968 — flip `link.party(state_code, p.party_eci_code, p.party_short)` -> `link.party(p.party_id)`. Wrap with `{#if href}<a href={href}>...</a>{:else}<span>...</span>{/if}` to handle UNK.
7. `frontend/src/routes/Constituency.svelte` line 571 — same flip: `link.party(c.party_id)`. Drop the `{#if c.party_eci_code && state_code}` guard (no longer needed; new builder takes party_id).
8. `frontend/src/contracts/url-namespace-disjointness.test.ts` — add `loadPartySlugs()` reading parties.csv; extend the `describe` block to 6-way pairwise disjointness; add internal-uniqueness assertion.
9. `frontend/src/lib/links.test.ts` — DELETE the 3 existing partyInState/party tests. ADD: `link.party("parties.IN.INC") === "/parties/inc"`, `link.party("parties.IN.IND") === "/parties/independent"`, `link.party("parties.IN.NOTA") === "/parties/nota"`, `link.party("parties.IN.UNK") === null`, `link.party("parties.IN.JDU") === "/parties/jdu"`, `link.parties() === "/parties"`. Round-trip: every party_id in parties.csv except UNK round-trips through `partyIdFromSlug(partyIdToSlug(pid)) === pid`.
10. `frontend/src/lib/slug.test.ts` — DELETE existing `partySlug()` tests; ADD `partyIdToSlug` + `partyIdFromSlug` tests with the 5 cases above.
11. `docs/architecture/frontend/url-grammar.md` — append ADR-0053 section under the existing ADR-0052 receipts. Update the "Final route grammar" table: remove the "Party-in-state" row; add "Parties index" + "Per-party detail" rows. Update the `RESERVED` enumeration to swap `party` for `parties`. Update the "Strengthened collision invariant" para from 5-way to 6-way.
12. `docs/architecture/frontend/party-rendering.md` — NEW. Holds the binding contract for PartyPill adoption (the standardisation rule for PR-2 to enforce). Sections: (a) PartyPill is the SINGLE coloured party-rendering primitive; (b) every citizen-facing party reference renders via PartyPill and links to `/parties/<slug>` unless explicitly excluded; (c) explicit exclusions list (KPI numerators, sort column headers, breadcrumb labels); (d) tooltip contract pointer (forward to PR-1's PartyTooltip component); (e) 3-tier colour resolver pointer (forward to existing colours.md); (f) missing-symbol rule ("show symbol if present; if absent, left-align short, no placeholder, no initials"). 80-120 lines, Diataxis-aligned.
13. `docs/reference/decision-index.md` — add ADR-0053 row pointing to the url-grammar.md anchor.
14. Note in [/memories/repo/yen-gov-party-resolver.md](../memories/repo/yen-gov-party-resolver.md) — add a 5-line "URL grammar" subsection: canonical = `/parties/<lowercased party_id tail>`; sentinels = `independent`/`nota`/no-page-for-UNK; reserved = `parties` (plural).

**Acceptance gates**:
- svelte-check 0 new errors vs origin/main baseline (14 pre-existing per cheatsheet).
- vitest: all green; new disjointness + links tests pass.
- pytest: equal-to-baseline (no backend changes; 32 chronic fails unchanged).
- Browser smoke: navigate `/parties` + `/parties/inc` + `/parties/independent` + `/parties/nota`, confirm stub pages render with breadcrumb + H1 + "Coming soon". Confirm `/tamil-nadu` party-totals table links still work (they now point at `/parties/<slug>` and resolve to the stub).
- Negative smoke: `/parties/unknown` and `/tamil-nadu/party/dmk-5` (old shape) both fall through to NotFound — confirm.

**Stop conditions**: any svelte-check NEW error; any disjointness assertion red (the new partySlugs ⊥ stateSlugs etc.); any callsite I missed (grep `link\.party(` after edits — must be ZERO matches of the 3-arg shape).

### PR-1 (subagent; dispatched after PR-0 merges)

**Branch**: `feat/parties-pr1-pill-tooltip`. **Worktree**: `../yen-gov-parties-pr1`.

**Task**: ship the PartyPill hover tooltip per Jony A1+A2+A3+A4 verdict.

**Files**:

1. `frontend/src/lib/view-models/parties.ts` — NEW. `loadPartyMeta(party_id): Promise<PartyMeta | null>`. Reads parties.csv via DuckDB-WASM (`registerCsvAsTable("data_entities_parties_csv")` if not already registered; SELECT row WHERE party_id = ?). Module-level Promise cache keyed by party_id. `PartyMeta` interface: `{party_id, short, full, founded_year, dissolved_year, recognition_scope, home_state_codes, symbol_asset, brand_colour, wikipedia, name_native_script, is_sentinel}`. Also export `loadAllPartiesMeta(): Promise<Map<string, PartyMeta>>` — bulk fetch + memoise (used by PR-3).
2. `frontend/src/lib/party-pill/PartyTooltip.svelte` — NEW popover sub-component. Props: `{party_id, anchor: DOMRect, onClose}`. Loads `loadPartyMeta(party_id)` on mount. Renders a fixed-position card with: PartySymbolGlyph (only if `symbol_asset` non-null, fallback="silent"), short in semi-bold, full as body text, founded line ("Founded YYYY") only if `founded_year`, dissolved line only if `dissolved_year`, recognition badge (lucide `landmark`), native_script italic line if populated, wiki external-link icon at bottom-right (lucide `external-link`) when `wikipedia` non-null. Position: `fixed`, edge-clamped against viewport (mirror `ChartTooltip.svelte`). `pointer-events: auto` (popover is interactive — wiki link must be clickable). Background paper-neutral; no party-colour fill on the card body.
3. `frontend/src/lib/party-pill/PartyPill.svelte` — extend. Add state for `tooltipOpen: boolean` + `tooltipAnchor: DOMRect | null`. Add `onMouseEnter`, `onMouseLeave`, `onFocus`, `onBlur` handlers + click handler that toggles pin state. While `tooltipOpen` true AND `party_id` non-null AND `party_id !== "parties.IN.UNK"` (no tooltip for unresolved), render `<PartyTooltip {party_id} anchor={tooltipAnchor} onClose={...}/>`. Don't break the existing `onclick` semantics (still routes via the click prop). Click without a click prop = pin-toggle only. Hover-leave with mouse OR Escape key OR click-outside dismisses an unpinned tooltip. Pin remains until explicit dismiss.
4. `frontend/src/lib/party-pill/PartyTooltip.test.ts` — NEW. happy-dom render tests: (a) renders symbol when asset present; (b) does NOT render symbol when asset null (no placeholder); (c) renders founded line only when populated; (d) renders wiki link with `target="_blank" rel="noopener noreferrer"`.
5. `frontend/src/lib/party-pill/PartyPill.test.ts` — extend with: (a) hover opens tooltip; (b) click pins; (c) Escape closes; (d) UNK does NOT open tooltip; (e) tooltip closes on `onMouseLeave` when not pinned.
6. `frontend/src/lib/view-models/parties.test.ts` — NEW. Mock duckdb registerCsvAsTable + query per CLAUDE.md §15 carve-out for canonical-store loaders. Tests: cache hit returns same promise; null returned for unknown party_id; bulk fetch populates the Map.

**Acceptance gates**:
- vitest: new tests green; existing PartyPill tests still green.
- svelte-check 0 new errors.
- Browser smoke: open `/tamil-nadu`, hover over a party_short cell in the party-totals table — popover appears with party metadata. Click pins it. Esc closes. Open `/tamil-nadu/elections/assembly-2026/ac/<some-ac>`, hover over a candidate's party_short — popover. Negative: hover over an IND/NOTA cell — popover renders (without symbol/wiki); hover over an UNK cell — no popover.

**Stop conditions**: tooltip renders a placeholder symbol for a missing asset (FORBIDDEN per Jony A3 + user instruction); tooltip fabricates a "Chief" field (FORBIDDEN per Jony A2); tooltip uses `@floating-ui` or any new npm dep.

### PR-2 (subagent; parallel with PR-1; file-disjoint by design)

**Branch**: `feat/parties-pr2-adopt-partypill`. **Worktree**: `../yen-gov-parties-pr2`.

**Task**: enforce the [docs/architecture/frontend/party-rendering.md](../docs/architecture/frontend/party-rendering.md) contract on every surface that currently renders party as plain text.

**Files** (consumer surfaces only — never touches PartyPill itself):

1. `frontend/src/routes/CompareElections.svelte` — replace the 2 plain-text `<td>{r.from_party ?? "—"}</td>` and `<td>{r.to_party ?? "—"}</td>` cells with `<PartyPill party_id={r.from_party_id} party_short={r.from_party ?? "—"} size="sm" onclick={() => navigateTo(link.party(r.from_party_id))}/>` (and same for `to_party`). Wrap pill click in `event.stopPropagation()` so it doesn't trigger the row click. When `link.party(...)` returns null (UNK), skip the onclick. Also fix the `change_label` "Flip BJP → DMK" / "Hold DMK" rendering: it stays text BUT each party_short token inside it becomes a PartyPill inline (split on the arrow / hold-prefix; render party tokens as pills, glue as text).
2. `frontend/src/lib/charts/IndiaPartyMap.svelte` — legend currently shows party_short as text. Replace each legend entry with `<PartyPill size="sm" {party_id} {party_short} {row} onclick={() => navigateTo(link.party(party_id))}/>`. Confirm the legend already has party_id available via the existing palette resolver (it does — verified line 220 `resolvePartyPalette`).
3. `frontend/src/routes/NationalElection.svelte` — top-parties bar (or whatever the equivalent post-W3c shape is). Replace bespoke party_short labels with `<PartyPill>`. Find via grep on `party_short` inside the file.
4. `frontend/src/lib/PartyBar.svelte` — segment labels currently bespoke spans. Replace each segment's clickable label with `<PartyPill size="sm" muted={hidden_parties.has(p.party_id)} onclick={() => onToggleHidden?.(p.party_id)}>` — note: in PartyBar the click toggles muted state, NOT navigation. Documented exception in party-rendering.md (mute toggle is a chart-affordance not a citizen-link). The party SHORT label inside a separate `<a href={link.party(p.party_id)}>` next to each pill — separates the mute toggle (pill click) from the navigate-to-detail (label click). Two visible affordances per row.
5. `frontend/src/lib/WinnerBadge.svelte` — wrap the party-short text label with `<a href={link.party(winner.party_id)}>` (party_id already available on winner row). Keep the accent stripe + glyph as-is; just make the short clickable.
6. `frontend/src/routes/StateOverview.svelte` line 968 — already flipped to `link.party(p.party_id)` in PR-0. NOW wrap the inner `{p.party_short}` text in a `<PartyPill size="sm" party_id={p.party_id} party_short={p.party_short} row={p}/>`. Drop the outer `<a>` element — pill handles its own click.
7. `frontend/src/routes/Constituency.svelte` line 571 — same wrap; outer `<a>` dropped; PartyPill handles click.
8. `frontend/src/contracts/party-rendering.test.ts` — NEW Tier-A contract test. Walks every `.svelte` file under `frontend/src/routes/` and `frontend/src/lib/charts/` (excludes party-pill itself + DevChartsSandbox). For each file, greps the AST for raw `{...party_short}` / `{...party_id}` template tokens NOT preceded by `<PartyPill` or `<a href={link.party(`. Reports per-file violations. Allowlist: `[]` initially (every violation must either be fixed or added to the allowlist with a comment justifying the exception). The 4 doctrinal exceptions from party-rendering.md (KPI numerators, sort column headers, breadcrumb labels, tooltip body itself) go in the allowlist with cited justifications.

**Acceptance gates**:
- vitest: party-rendering.test.ts green (zero violations).
- svelte-check 0 new errors.
- Browser smoke: navigate `/compare/elections/tamil-nadu/assembly-2021/assembly-2026` (USER'S ORIGINAL URL) — every party cell is now a coloured pill, hover shows tooltip (PR-1 must have landed; if PR-1 not yet merged, tooltip is the bare existing pill behaviour and that's OK), click navigates to `/parties/<slug>` stub. Click on a constituency row still drills to the constituency page (event.stopPropagation works). Smoke: `/tamil-nadu`, `/tamil-nadu/elections/assembly-2026`, `/`, `/t/elections/general-2024` — all party renders are pills.

**Stop conditions**: party-rendering.test.ts has any unfixed violation; row click drills through pill click (event.stopPropagation missing); a surface gains a new bespoke party-rendering component instead of adopting PartyPill.

### PR-3 (subagent; Wave 2, parallel with PR-4)

**Branch**: `feat/parties-pr3-parties-index`. **Worktree**: `../yen-gov-parties-pr3`.

**Task**: build the `/parties` index page body. Replace the PR-0 stub.

**Files**:

1. `frontend/src/routes/PartiesIndex.svelte` — full body. Header: H1 "Parties". Search box (controlled state, filters the list on `party_short` + `party_full` + `aliases` substring match, case-insensitive). Filter chip row: "All" / "National" / "State" / "Unrecognised registered" (4 chips; click toggles `recognition_scope` filter). Alphabetical letter rail: A-Z chips that scroll-jump to a section anchor. Body: alphabetically grouped sections (`A` / `B` / ...), each section a grid of PartyPill rows. Each row: `<PartyPill size="md" {party_id} {party_short} {row} onclick={() => navigateTo(link.party(party_id))}/>` + the party full name in slate-700 next to it + recognition badge chip. Sentinels (IND, NOTA) appear at the top in their own "Special" section above 'A'. UNK does NOT appear.
2. `frontend/src/lib/view-models/parties.ts` — extend (created in PR-1). Add `loadAllParties(): Promise<PartySummary[]>` — `PartySummary = {party_id, slug, short, full, recognition_scope, home_state_codes, founded_year, symbol_asset, brand_colour, aliases, is_sentinel}`. DuckDB query: `SELECT * FROM data_entities_parties_csv ORDER BY short`. Cached. The `slug` field is derived via `partyIdToSlug(party_id)` at mapping time; rows where slug is null (UNK) are filtered out.
3. `frontend/src/routes/PartiesIndex.test.ts` — happy-dom render test. Mock view-model. Assert: 4 filter chips render; alphabetical sections; clicking the "National" chip narrows to national-recognised parties only; search "DMK" narrows to 1-2 rows including the literal DMK row; sentinels appear in "Special" section.
4. `frontend/src/lib/view-models/parties.test.ts` — extend with `loadAllParties` tests: returns sorted by short; excludes UNK; sentinels included.
5. `frontend/e2e/parties-index.spec.ts` — NEW Playwright. Navigate `/parties`, assert: H1 visible; INC pill visible; click INC pill -> URL is `/parties/inc`; back; filter chip "State" reduces visible count; search "DMK" narrows; alphabetical letter chip "D" jumps to D section.

**Acceptance gates**:
- vitest green.
- Playwright green on at least 1 chromium row (the new spec).
- svelte-check 0 new errors.
- Browser smoke: navigate `/parties`. Confirm: 2200+ parties scrollable; search works; chips filter; clicking a pill navigates to the per-party page (which is still the stub if PR-4 hasn't merged — that's OK; smoke just verifies routing).

**Stop conditions**: page renders the UNK sentinel (must be filtered out); search is case-sensitive (must be case-insensitive); a citizen on a slow phone scrolling the full 2259-row list crashes the page (virtualise if measured FPS <30 on mid-tier Android — defer the implementation choice; document the perf measurement in the PR body either way).

### PR-4 (subagent; Wave 2, parallel with PR-3)

**Branch**: `feat/parties-pr4-party-detail-and-dualaxis`. **Worktree**: `../yen-gov-parties-pr4`.

**Task**: build the `/parties/<slug>` detail page per Jony spec. Build the new closed-renderer primitive `DualAxisBarLine.svelte`. Fold the ADR for the renderer extension inline.

**Files**:

1. `frontend/src/routes/Party.svelte` — full body. Replace the PR-0 stub. Sections per Jony verdict B1 (this order):
   - **(0) Breadcrumb**: Home > Parties > &lt;short&gt;.
   - **(1) Header card**: 80px coloured square (anchor=full-bleed, brand=ring, fallback=swatch, sentinel=grey-neutral) with party short in bold. To the right: H1 = party full name. Sub-line: `recognition_scope` chip (lucide `landmark`) + " · peak <N> LS seats in <YYYY>" computed from `loadPartyDetail.ls_history`.
   - **(2) Latest-of one-liners (one per body)**: ABOVE each chart. Format per Jony B7: `Lok Sabha (2024): **99 of 543 seats** · 21.2% vote share · ↓ from peak 415 in 1984.` Same for VS. If body has no data, omit the line + chart for that body (don't render an empty chart frame).
   - **(3) KPI strip 2×2 (mobile 2x2; desktop 1x4)**: LS seats won (cumulative across all ingested cycles), VS seats won (cumulative), Elections contested, Active range (`first_year - last_year`). All sourced from `loadPartyDetail.metadata` + history.
   - **(4) LS DualAxisBarLine chart**: X = election year, Y_left = seats (blue bar in party brand_colour), Y_right = vote_share_pct 0..100 (slate-700 line with dots). Header: "Lok Sabha — every election contested" + right-aligned "best: <N> seats in <YYYY>".
   - **(5) VS DualAxisBarLine chart**: parallel to LS. Header: "Vidhan Sabha — every state assembly election contested".
   - **(6) Strongholds top-10 per body**: list, not choropleth. Each row: constituency name + "won X of Y elections" + win-rate % + tiny inline W/L sparkline (▮▮▯▮▮). Two sub-sections: "LS strongholds" + "VS strongholds". Coverage caption per body: "Strongholds computed over 1999-2024 LS / 2008-2026 AE; pre-coverage history not yet ingested."
   - **(7) Metadata footer**: glyphs from lucide via `<TopicIcon>`. Founded (calendar), Dissolved (x-circle, only if non-null), Recognition (landmark), Home states (map-pin, one per state in `home_state_codes`), Native script (languages, italic), Wiki (external-link as an anchor). Lineage chips at the bottom: `predecessor_party_ids[]` chips (each clickable to its `/parties/<slug>`) labeled "Descended from"; `successor_party_ids[]` chips labeled "Split into". `aliases` as small chips at the very bottom labeled "Also known as".
   - Empty / sentinel handling: if `is_sentinel`, sections (4) (5) (6) hide the methodology coverage caption ("Independent / NOTA totals do not represent a single political actor"). Per Hans verdict 5 — page renders but with honest framing.
2. `frontend/src/lib/charts/DualAxisBarLine/DualAxisBarLine.svelte` — NEW. Pure d3 + Svelte. Props: `bars: {period_label, value: number}[]`, `line: {period_label, value: number}[]`, `bar_color: string`, `line_color?: string` (default `#334155` slate-700), `bar_y_label?: string`, `line_y_label?: string`, `bar_format?: (n) => string`, `line_format?: (n) => string`, `height?: number` (default 360), `min_year_label_gap?: number` (mobile thinning per Jony B6). Internal: shared X scale (ordinal on period_label sorted ascending), left Y linear (0..max(bars)), right Y linear (0..max(line, 100) — capped at 100 if line values are percentages, detected via `line_format` containing "%"). Bars drawn first, line + dots second. X-axis label thinning: at viewport <640px show every Nth label; tap a bar reveals year + both values via popover (reuse `ChartTooltip` shape).
3. `frontend/src/lib/charts/DualAxisBarLine/DualAxisBarLine.test.ts` — NEW unit. happy-dom render with fixture `{bars: [...], line: [...]}`. Assert: bar count matches, line path has correct # of points, mobile thinning applies on simulated narrow viewport.
4. `frontend/src/lib/view-models/party-detail.ts` — NEW. `loadPartyDetail(party_id): Promise<PartyDetailViewModel>`. Shape:
   ```typescript
   interface PartyDetailViewModel {
     metadata: PartyMeta;
     ls_history: { year: number; period_label: string; seats: number; vote_share_pct: number | null; contested: number | null }[];
     vs_history: { year: number; period_label: string; seats: number; vote_share_pct: number | null; contested: number | null }[];
     ls_strongholds: { entity_id: string; constituency_name: string; state: string; wins: number; contested: number; results: ("W" | "L")[] }[];
     vs_strongholds: same shape;
     totals: { ls_seats: number; vs_seats: number; elections_contested: number; first_year: number; last_year: number; peak_ls_seats: number; peak_ls_year: number };
   }
   ```
   Queries against `read_csv('/data/data/datapoints/electoral/*_election_results.csv', ...)` (per-state long-format aggregate, post-X1a-fu2 shape). Strongholds query against `read_csv('/data/elections/{assembly,parliament}/state=*/election=*/summary.csv', ...)` per Max section 6. Memoise per party_id.
5. `frontend/src/lib/view-models/party-detail.test.ts` — NEW. Mock duckdb registerCsvAsTable + query. Tests: (a) returns null for unknown party_id; (b) ls_history sorted ascending by year; (c) peak_ls_year correctly computed; (d) sentinel party returns history but with `vote_share_pct = null` (sentinels lack aggregate vote-share by design); (e) cache hit returns same promise.
6. `frontend/src/routes/Party.test.ts` — NEW. happy-dom render with mocked loader. Tests: (a) renders header card with party brand_colour fill for anchor (BJP); (b) renders ring for brand-tier (BJD); (c) renders grey for sentinel (NOTA); (d) hides chart section when body has no data; (e) renders "peak X in YYYY" sub-line correctly; (f) lineage chips render as anchors to `/parties/<predecessor-slug>`; (g) UNK slug -> NotFound (link.party(UNK) returns null already; the route itself goes to NotFound when params.slug fails to resolve).
7. `frontend/e2e/party-detail.spec.ts` — NEW Playwright. Navigate `/parties/inc`. Assert: H1 = "Indian National Congress"; header card has Congress-blue avatar; KPI shows 4 numeric tiles; LS chart visible (svg with bars + line); peak label "best: 415 seats in 1984" (or equivalent from the data); VS chart visible; strongholds list has ≥1 row; metadata footer has wiki link. Second nav: `/parties/dmk` — DMK red avatar; LS section may have a "Pre-1999 LS history not yet ingested" caption if applicable.
8. `docs/concepts/schema-is-the-design-system.md` — extend the "Closed renderer set" enumeration with `DualAxisBarLine`. Add inline ADR-0053 doc block per the doctrinal contract (the ADR lives INSIDE the concept doc per the no-new-ADR-files rule + decision-index keep-receipts).
9. `docs/architecture/frontend/charts/dual-axis-bar-line.md` — NEW thin subsystem doc (~30 lines) per the existing `frontend/src/lib/charts/` convention. Contract: bars, line, dual Y axes, mobile thinning, tap-detail. "See also" cross-link to ADR-0053 in schema-is-the-design-system.md.
10. `docs/reference/decision-index.md` — append ADR-0053 row (folded into schema-is-the-design-system.md anchor).

**Acceptance gates**:
- vitest green (Party.test + party-detail.test + DualAxisBarLine.test).
- Playwright green on chromium + mobile-pixel-5 for party-detail.spec.
- svelte-check 0 new errors.
- Browser smoke: `/parties/inc` matches the screenshot the user attached (Congress-blue avatar, INC header, "peak 415 LS seats in 1984" sub-line, 4-tile KPI strip, LS bar+line chart matching the screenshot shape, VS chart below, top-10 strongholds, metadata footer with wiki link). `/parties/bjp`, `/parties/dmk`, `/parties/aiadmk`, `/parties/cpim` (note: `parties.IN.CPIM` not `CPI_M`) all render. `/parties/nota` + `/parties/independent` render with the sentinel framing (no symbol, no wiki, no founded; honest one-liner). `/parties/unknown` -> NotFound.

**Stop conditions**: chart fabricates pre-1999 LS data (must surface the coverage caption); DualAxisBarLine extracts logic from `StackedTrendV2` instead of being a standalone closed renderer (Hans+Max would object — file the deviation as STOP-AND-SURFACE if mid-PR you discover the composition makes more sense; do NOT silent-refactor); ADR-0053 is omitted from schema-is-the-design-system.md.

## 6. Execution block

**Orchestrator topology** (per user-memory "Autonomous 16-PR plan orchestration"):

- Orchestrator stays in MASTER worktree. Master is on `main` throughout.
- PR-0 dispatched to ORCHESTRATOR's own sub-worktree (`../yen-gov-parties-pr0`); orchestrator implements PR-0 directly because the rip-and-replace touches 14 files and 1 PR is the right cut size.
- Wave 1: PR-1 + PR-2 dispatched in PARALLEL to two new sub-worktrees via stateless subagents (`runSubagent` with default agent, NOT persona — execution work).
- Wave 2 after Wave 1 merges: PR-3 + PR-4 dispatched in PARALLEL.

**Per-PR worktree hygiene**: `git worktree add ../yen-gov-parties-pr<N> -b feat/parties-pr<N>-<slug> origin/main`. Subagent's brief includes the absolute worktree path. After merge: `git fetch origin --prune && git worktree remove --force ../yen-gov-parties-pr<N> && git branch -D feat/parties-pr<N>-<slug> && git worktree prune`. Cosmetic `'main' is already used by worktree at ...` error from `gh pr merge` is expected and handled by manual `git push origin --delete <branch>`.

**Master-worktree-collision protection** (per user-memory): orchestrator commits + pushes plan-doc edits IMMEDIATELY; never holds uncommitted master-worktree edits across subagent dispatches. Untracked files in master at session start (`boundary_layer.csv` + `goa/all.geojson`) are parallel-agent WIP — DO NOT TOUCH.

**Stop conditions for orchestrator** (any -> STOP-AND-SURFACE per CLAUDE.md §10):
- Hans's verdict on slug shape is overridden by something I read mid-execution.
- A subagent's PR diff suggests the rip-and-replace breaks a citizen-facing surface that was not in my analysis (e.g. a route I missed).
- A persona insists on revisiting a verdict that's locked in section 1.

**Persona consultation post-launch**: NOT required between PRs. The 4 verdicts from 2026-06-12 cover the design surface end-to-end. Hans + Max sign-off on the DEFERRED items in section 2 is needed BEFORE those ship — but those are not in this plan.

## 7. Closure ledger (closed 2026-06-12)

**Plan complete.** All 5 PRs landed atomically on `origin/main` within hours of plan-doc commit. The user's URL (`https://miztiik.github.io/yen-gov/compare/elections/tamil-nadu/assembly-2021/assembly-2026`) now renders party tokens as coloured PartyPills that hover-tooltip with full metadata and link to `/parties/<slug>` indiavotes-style detail pages.

| PR | Branch | Merge SHA | Wave | Status | Notes |
|---|---|---|---|---|---|
| PR-0 | feat/parties-pr0-doctrine-and-rip | `25f48362` | 0 | MERGED | orchestrator-authored. 14 files (10 code + 1 disjointness test + 3 docs). Atomic rip-and-replace: `/<state>/party/<slug>` route + legacy Party.svelte body + `partyInState` + 3-arg `party` + `partySlug` helper DELETED; new `/parties` index + `/parties/<slug>` STUB routes + new `partyIdToSlug` + `partyIdFromSlug` + 6-way disjointness contract + ADR-0053 in url-grammar.md + new party-rendering.md ADDED. 2 callsites flipped (StateOverview L968 + Constituency L571). 5 sentinel/disambiguator overrides locked: IND -> independent, AC -> arunachal-congress, GOA -> goemcarancho-otrec-astro, MAHAD -> mahakranti-dal, UNK -> no page. Gates: svelte-check 30/30 baseline, vitest 5599/0/15. |
| PR-1 | feat/parties-pr1-pill-tooltip | `9960adf6` | 1 | MERGED | subagent. 7 files (PartyTooltip.svelte NEW + PartyPill.svelte extended + view-models/parties.ts NEW with loadPartyMeta + loadAllPartiesMeta + 3 test files + 1 index.ts re-export). Hover/focus/click-pin popover hand-rolled per ChartTooltip pattern, no @floating-ui dep. Tooltip drops "Chief" per Max section 3 (no column, don't fabricate). Missing-symbol = left-align short, no placeholder. Gates: 30/30, 5599/0/15. **Deviation**: tests are pure-helper style (project has no @testing-library/svelte); loader bypasses `dim_parties` view (missing 7 of 18 columns) for direct CSV read via parties-palette.ts precedent. |
| PR-2 | feat/parties-pr2-adopt-partypill | `b33016d9` | 1 | MERGED | subagent. 10 files (8 surfaces + party-rendering contract test + colors/party-row.ts helper). Adopted PartyPill on CompareElections, StateOverview, Constituency, PartyBar, WinnerBadge, GallagherDisproportionality, Psephlab, Settings. Contract test walks every .svelte under routes/ + lib/charts/ and asserts party_short / party_id refs are PartyPill-wrapped or carry the `data-allow="..."` allowlist attribute. Gates: 30/30, 5599/0/15. **Deviations**: IndiaPartyMap legend doesn't exist (party_short only in tooltip JS string, stripped by script-block excluder); NationalElection top-parties = PartyBar already (covered transitively); change_label deferred per brief; 3 extra files in scope (GallagherDisproportionality, Psephlab, Settings) fixed inline rather than allowlisted. |
| PR-3 | feat/parties-pr3-parties-index | `8a909a43` | 2 | MERGED | subagent. 5 files (PartiesIndex.svelte full body + parties.ts extended with loadAllParties + 2 test files + Playwright e2e). 2348-row alphabetical index with search box + 4 recognition chips (All 2348 / National 18 / State 60 / Unrecognised 393 / sentinels in "Special" section above 'A') + A-Z letter rail. UNK filtered. Gates: 30/30, 5626/0/15 (+27). Optional e2e shipped. **Caught a real bug** routed to PR-4: Party.svelte STUB destructured `{ slug }` instead of `{ params }` (router passes nested) — crash on every `/parties/<slug>` navigation. |
| PR-4 | feat/parties-pr4-party-detail | `827a7a97` | 2 | MERGED | subagent. 9 files (Party.svelte full body + party-detail.ts view-model + DualAxisBarLine.svelte NEW closed-renderer + 3 test files + Playwright + schema-is-the-design-system.md extended + new dual-axis-bar-line.md subsystem doc). 2843 insertions. Header card + KPI 2x2 + LS DualAxisBarLine + VS DualAxisBarLine + strongholds top-10 per body + metadata footer with lineage chips. Sentinel framing for IND / NOTA. "Party not found" for typo slugs (no JS crash). Smoke verified: `/parties/inc`, `/parties/bjp`, `/parties/nota`, `/parties/xyznotreal`. STUB destructure bug fixed in the rebuild. Gates: 30/31 (+1 a11y warning, descoped per CLAUDE.md §0a), 5652/0/15 (+26). **Deviations** (both honest-degraded-UX per CLAUDE.md §10 inline note pattern): (1) LS history synthesises from per-PC winner rows because publisher emits no per-party LS aggregate (vote_share + contested stay null at v1, bars only; coverage caption surfaces); (2) stronghold names show entity_id text because per-state CSV uses state-CODE namespace (`IN-PC-1976-S01-1`) but electoral.csv uses state-SLUG namespace — JOIN miss; both flagged as future-PR work, not silent degradation. |

**Total**: 5 PRs / 5 waves (PR-0 solo, Wave 1 PR-1+PR-2 parallel, Wave 2 PR-3+PR-4 parallel) / 45 files changed / ~5630 vitest passes across 195 files. Parallel agents from OTHER teams shipped 5 other PRs (#969, #970, #975, #976, FU#2) into main during the same window — file-disjoint, no collisions.

## 8. Distillation pointers

After this plan-doc moves to `docs/archive/plans/`, the durable findings live at:

- **URL grammar**: [docs/architecture/frontend/url-grammar.md](../docs/architecture/frontend/url-grammar.md) ADR-0053 + rejected-alternatives receipts (landed PR-0).
- **PartyPill standardisation contract**: [docs/architecture/frontend/party-rendering.md](../docs/architecture/frontend/party-rendering.md) (NEW; landed PR-0; PR-2 added 1 allowlist exception for the `<option>` HTML edge case).
- **DualAxisBarLine closed-renderer**: [docs/concepts/schema-is-the-design-system.md](../docs/concepts/schema-is-the-design-system.md) closed-renderer-extension log + [docs/architecture/frontend/charts/dual-axis-bar-line.md](../docs/architecture/frontend/charts/dual-axis-bar-line.md) subsystem doc (NEW; landed PR-4).
- **Slug derivation rule + sentinel overrides**: [frontend/src/lib/slug.ts](../frontend/src/lib/slug.ts) `partyIdToSlug` + `partyIdFromSlug` + `SENTINEL_SLUG_OVERRIDES` map; tested in `slug.test.ts` round-trip against the live 2259-row parties.csv corpus.
- **6-way disjointness contract**: [frontend/src/contracts/url-namespace-disjointness.test.ts](../frontend/src/contracts/url-namespace-disjointness.test.ts) ADR-0053 describe block.
- **PartyPill rendering**: [frontend/src/lib/party-pill/PartyPill.svelte](../frontend/src/lib/party-pill/PartyPill.svelte) (extended PR-1) + [frontend/src/lib/party-pill/PartyTooltip.svelte](../frontend/src/lib/party-pill/PartyTooltip.svelte) (NEW PR-1).
- **Party detail view-model**: [frontend/src/lib/view-models/parties.ts](../frontend/src/lib/view-models/parties.ts) (NEW PR-1 + extended PR-3) + [frontend/src/lib/view-models/party-detail.ts](../frontend/src/lib/view-models/party-detail.ts) (NEW PR-4).

Agent-only lessons (the recurring traps worth noting in `/memories/lessons.md` for future plans):

- **Real disjointness collisions ALWAYS surface during PR-0** when adding a new slug registry. GOA + MAHAD both fired at vitest-time exactly as the STOP-AND-SURFACE doctrine predicted. The cost of fixing them = +2 entries in `SENTINEL_SLUG_OVERRIDES` + 4 lines of test = trivial. The cost of NOT having the contract = a citizen-visible URL collision in production. The 6-way disjointness gate paid for itself within the same PR.
- **Router passes nested `params`, not flat destructure**. The PR-0 STUB shipped with `let { slug } = $props()` instead of `let { params } = $props()`, crashing on every navigation — caught only by PR-3's smoke. Future agent rule: when writing a new route-mounted Svelte component, GREP an existing sibling route (StateOverview / Explore / StateTopic) for the exact prop shape — don't trust a route-table parse function to flatten what it doesn't.
- **Per-state CSV state-code vs slug namespace divergence is a real ingestion-side bug surface for any cross-state party query** (PR-4 deviation #2). The long-format `<state>_election_results.csv` uses `IN-PC-1976-S01-1` (ECI state code) but `electoral.csv` uses `IN-PC-2008-andhra-pradesh-411` (state slug). Any future query that joins them needs a state-code-to-slug lookup. The deferred fix lives in the PR-4 PR body as a future-PR.
- **LS party-aggregate rows are missing from the per-state long-format CSVs** (PR-4 deviation #1). The publisher emits per-PC winner rows + per-(party,event) AE aggregate rows, but no per-(party,event) LS aggregate. PR-4 synthesises via COUNT over winner rows; vote_share + contested stay null. The proper fix is a backend ingest extension — out of scope here.

## 8. Verdict-source receipts

The 4 persona verdicts that authorise this plan were solicited 2026-06-12 (this session). Each verdict's full text is preserved in the chat-session-resources cache by message-id. The binding extracts are quoted in section 1; the rejected alternatives are quoted in section 2. If a future agent disputes a verdict in section 1, they must consult the original persona again and explicitly override with user sign-off — do NOT silently revisit.

User direction-quotes (intent-only, per CLAUDE.md §10 "no verbatim user prose in committed artifacts"):
- (2026-06-12) follow indiavotes model for parties.
- (2026-06-12) for the detail page, drop the by-year results table; keep only the seats-over-time + vote-share + strongholds charts.
- (2026-06-12) clicking PartyPill must lead to the party page.
- (2026-06-12) show party symbol if it is there; if absent, do NOT show a placeholder.
- (2026-06-12) jazz up the metadata footer with glyphs/icons.
- (2026-06-12) URL grammar must accommodate both regional + national parties; can't shove under /state.
- (2026-06-12) no strangler-fig nonsense; rip-and-replace; temporarily breaking things is acceptable.

## 9. Follow-up ledger — v1 honest-degradations closed (2026-06-12)

The two v1 honest-degradations flagged inline + in the PR-4 body have both shipped as standalone post-archive PRs. The five other "deferred follow-ups" (pre-1999 LS history, NOTA legal-context caveat, Wikidata P488 chief column, recognition-flip annotation strip, constituency-level strongholds choropleth) remain Hans/Max-territory awaiting separate plan-docs when prioritised.

| FU | Branch | Merge SHA | Closes | Notes |
|---|---|---|---|---|
| FU-A | feat/party-stronghold-state-slug-join | `b78d689a4` | PR-4 known-degradation #2 (strongholds show entity_id text) | 4 files (translator + test + view-model edit + test edit). NEW `frontend/src/lib/canonical/electoral-id-translator.ts` hand-authors the 36-row `ECI_TO_SLUG` map from `datasets/taxonomy/lgd_states.json` `.states[].{eci_st_code, slug}` (backend mirror at `backend/yen_gov/canonical/adapters/eci/state_slug.py`). View-model rewrites the stronghold→entity-JOIN seam from `WHERE entity_id IN (...)` to a natural-key 4-tuple JOIN on `(entity_kind, delim_year, state, eci_no)`. **Path B (pure string-substitution) was attempted first and abandoned** mid-execution: electoral.csv's suffix is LGD-sequential synthetic ID for 92% of 2008 rows and `eci<eci_no>` for 8% (commit `55dc91946` dual-suffix convention) — not derivable from per-state-CSV's eci_no alone. Path A (natural-key) is the only structurally-correct bridge per CLAUDE.md §10 + OWID natural-key JOIN conventions. Gates: svelte-check 30/30 baseline; vitest 298/298 focused (24 translator + 27 party-detail); pytest baseline-equal; browser smoke verified DMK 17/20 + BJP 18/20 strongholds resolved (35/40 = 87.5%). **Residual 12.5%** (DMK: `IN-PC-2008-S22-{10,19,25}`; BJP: `IN-PC-2008-S04-{2,3}`): chronic data gap in electoral.csv — tamil-nadu PC 2008 partition has 13/39 rows with `eci_no=0` placeholder. JOIN correctly returns no rows; UI falls back to empty-string via existing lookup-miss path (no regression). |
| FU-B | feat/party-ls-aggregate-ingest | `9345e62eb` | PR-4 known-degradation #1 (LS vote-share + contested null) | 47 files (4 backend code + 1 backend test NEW + 1 regen tool NEW + 2 taxonomy + 1 ops index + 36 per-state CSVs + 2 frontend). NEW `parliament_rollup_observations()` + `PCContestSummary` in `backend/yen_gov/canonical/adapters/eci/rollups.py` mirrors `state_rollup_observations()` for the LS body. Call-site lives in `eci_ls._envelope_from_results` (NOT `parliament_results.py` — orchestrator brief was wrong about the wiring; the actual seam is the shared envelope builder feeding the per-state CSV writer). NEW indicator `party-contested-pcs` + NEW concept `contested-pcs` in `datasets/taxonomy/{indicators,concepts}.json` (the concept split is forced by `tier_b_one_indicator_per_concept` — can't share the AC sibling's `concept_id="contested"` because unit_canonical differs). State-scoped per Hans-verdict locked in this follow-up (mirrors AC; reuses `party_rollup_entity_id`); frontend SUMs across states in SQL via a CTE with votes-weighted national share `SUM(party_votes) / SUM(state_votes) * 100`. NEW `tools/regen_ls_party_rollups.py` is the structurally-honest fix for the writer retired in X1a-fu2-D commit (`bfa9aef2a`, 2026-06-07) — bounded, re-runnable, mirrors the deleted one-time rip pattern. **Regen output: 27,449 new rollup rows across 6 LS cycles** (1999 +2629, 2004 +3256, 2009 +4248, 2014 +4542, 2019 +4770, 2024 +8004). Gates: focused pytest 24/24; full pytest 28/1997/20 (below the 29-failure chronic ceiling); vitest 298/298; svelte-check baseline. Browser smoke verified BJP/DMK/INC LS charts now render non-null vote-share across all 6 cycles. **Residuals**: BJP 211 vs real 240 + INC 82 vs real 99 LS 2024 seat counts (party-id resolver misses to `parties.IN.UNK`); state-level `electors-total` + `turnout-pct` missing for LS 2024 (candidacies.csv fallback doesn't carry `total_electors`) — both close as resolver coverage improves + pc-* dim row lift lands (separate Hans+Max-territory follow-ups). Small surgical extension in `backend/yen_gov/sources/eci/ls_ge_tcpd.py` to accept both "Parliament Election (GE)" and "Lok Sabha Election (GE)" Election_Type labels (TCPD relabel on the 2026-06-05 snapshot was blocking re-ingest). |

**Total**: 2 follow-up PRs / 51 files changed / 27,747 net insertions / 0 plan-doc revisions required (both PRs faithful to the PR-4 known-degradation framings).

**Agent-only lessons from FU-A + FU-B** (worth promoting to `/memories/lessons.md`):

- **Translator briefs MUST verify electoral.csv suffix conventions before designing the translator** (FU-A). Orchestrator saw `eci192` in one TN sample and `167` in the eci/identity.py docstring — but didn't sample broadly enough to see the 92% LGD-sequential dominant pattern from commit `55dc91946`. The first subagent (Explore-class, read-only) correctly STOPped after the pre-flight verify revealed pure string-substitution was impossible. Forward rule: when authoring a translator brief for any synthetic-ID-bearing CSV pair, the brief MUST include a "sample 50 rows from each side across 3 states × 2 delim_years and decide based on what's actually there" step BEFORE the design — don't trust docstring examples.
- **Persona-class subagents (Andre/Hans/Max/Fowler/Gregor/Jony/Citizen) AND Explore are READ-ONLY**, no edit/terminal tools. Dispatch execution work to the default agent. This trips up every multi-PR plan that doesn't explicitly carve persona-territory work into "consult-then-default-agent-executes" — log it in user-memory patterns.md (already there from 2026-06-11 entry, but the friction repeats).
- **Brief's "writer plugs in at `parliament_results.py`" was wrong**; actual seam is `eci_ls._envelope_from_results` (FU-B deviation #1). The Explore subagent correctly identified `state_rollup_observations` as the AC analogue but missed that the call-site routes through the shared envelope builder, not the per-event reingest module. Forward rule for ingest-extension briefs: the brief must include "trace the writer-call-chain end-to-end starting from where the CSV physically lands" as a verify step, not "find the function that looks like it should be the hook".
- **The 16.67% RPA Section 158 forfeiture threshold is the AC + LS shared constant**; mirror it explicitly in the LS rollup (FU-B). Don't re-derive; reuse the AC constant.
- **Concept registry rejects (concept_id, entity_kinds) tuples that already exist** — the `tier_b_one_indicator_per_concept` gate (FU-B). When adding a sibling indicator at a different entity grain (PCs vs ACs), a NEW concept_id is required even when the semantic meaning is identical. Brief authors should pre-check the concept registry for collisions before declaring the indicator name.
- **DuckDB-WASM row-tuple IN clause `(col1, col2) IN ((a, b), (c, d))` IS supported** (FU-A) — the brief flagged this as a potential STOP condition but it worked first try. Useful precedent for any future natural-key JOIN.

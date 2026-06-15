# Party-page citizen fixes (post-reimagination, citizen-readable corrections wave 2)

**Last Updated**: 2026-06-15
**Level**: 4 (cross-cutting: D7 width-cap migration touches ~22 routes; D12 sticky-breadcrumb audit touches every route; D9 render swap; D11 spans copy + VM cap; per-row scope spans Level-1 to Level-3)

## Section 0 - Operating contract

### 0.1 Why this plan exists

The 11-PR party-page reimagination ([docs/archive/plans/20260614-party-page-reimagination-plan.md](../../archive/plans/20260614-party-page-reimagination-plan.md)) shipped. The user's 2026-06-15 deployed-site walkthrough surfaced 13 concrete defects. D1-D9 are carried from the previous draft of this plan; D10-D13 were named in the 2026-06-15 review and are new in this rewrite.

- D1  Founded year missing for most parties (952 of 2776 rows have null `founded_year` in [datasets/data/entities/parties.csv](../../../datasets/data/entities/parties.csv); national parties 3 of 19 missing - BSP / CPI(M) / NPP; state-recognised 11 of 73 missing).
- D2  Recognition pill on the header renders text only; the ECI party-symbol image (broom for AAP, lotus for BJP, etc.) does not appear inline.
- D3  The landmark + flag icon glyphs inside `PartyCurrentStrength` and `PartyAllianceContext` render as empty 16x16 squares (root cause: `<img src="/icons/X.svg">` cannot inherit `currentColor` against stroke-less / fill-less Lucide-style SVG source).
- D4  Wikipedia link in `PartyAboutCard` is bare text; the asset [frontend/public/icons/wikipedia.svg](../../../frontend/public/icons/wikipedia.svg) does not exist.
- D5  The 10-cell `StrongholdDotStrip` (W = brand fill, L = hollow ring, DNC = hatch) under each stronghold row is not parseable; the citizen-readable replacement is a one-line tally `State - Constituency - won N of M times, last YYYY`.
- D6  In `DualAxisBarLine` composite mode, the left-Y `0.0%` label overlaps the x-axis baseline.
- D7  The page caps at `max-w-5xl` on a wide monitor; the cross-route audit found 6 cap values across ~22 routes with no shared primitive (the user has flagged the width-discipline gap twice).
- D8a Lifetime stronghold rows are not clickable to the per-PC / per-AC page.
- D8b The per-PC route exists via [frontend/src/routes/Constituency.svelte](../../../frontend/src/routes/Constituency.svelte) shape #3 but there is no `link.pc()` builder in [frontend/src/lib/links.ts](../../../frontend/src/lib/links.ts).
- D8c The 320x360 `PartyStrongholdMap` thumbnail next to the strongholds list is unreadable at that size.
- D9  The page's bottom-of-page `PartySourcesStrip` collapses to a 264-row table with hundreds of "ECI / Statistical Report Section 10 - <state> AcGenOctYYYY" rows. Out-of-family with the rest of the app (StateOverview, Yenask, every other chart use the shared `<SourceList>` publisher-pill paragraph). The OWID-aligned standard already documented at [docs/concepts/data-provenance.md](../../concepts/data-provenance.md) (`dedupeToPills` -> one pill per `(producer x series-family)`) is the binding pattern; the existing render on `/kerala/elections/assembly-2026` (`SOURCES - Source: Rajya Sabha Secretariat (Government of India) (2023-08-01)`) is what the party page must adopt.
- D10 The "State Assembly - every election contested" vote-share chart x-axis is unreadable: year labels collide into `19657389...`. Distinct from D6 (D6 is the y-axis `0.0%`; D10 is x-axis density). Two-fix scope: immediate skip+rotate (PR-10) and Level-3 range-brush primitive for future-proofing as the corpus widens (PR-14).
- D11 The "Who they ride with" alliance ledger lists 8 jurisdictions including pre-poll arrangements from 2021 that no longer hold. Indian pre-poll alliances rarely survive post-poll; 10-year-old alliances are not citizen-relevant. Time-cap the displayed list AND delete the 4 italic in-page meta-disclaimers (2 in `PartyCoverageBadge` consumed by PR-9, 2 in `PartyAllianceContext.svelte` + `PartyCurrentStrength.svelte`) - the duplicated cycle-coverage text moves to a single docs page.
- D12 `/parties/<slug>` has NO breadcrumb (e.g. `/kerala/elections/assembly-2026` shows `Home > Kerala > Kerala elections > assembly-2026`; `/parties/bjp` shows nothing). The `partyCrumbs` builder is already wired into the router via [frontend/src/main.ts](../../../frontend/src/main.ts) line 158; [frontend/src/routes/Party.svelte](../../../frontend/src/routes/Party.svelte) simply never mounts `<Breadcrumb>`. The user's framing extends this to a GLOBAL pass: every route that has a route-crumbs builder MUST mount the shared sticky `<Breadcrumb>` primitive; audit any bespoke implementations and unify.
- D13 Mint one docs page that consolidates the 4 inline italic disclaimers retired by D11 + the alliance recency cap rationale from D11. Party page carries one quiet `About this page ->` link in the footer. Deletion-first: the inline italics retire because they now have a single home, not because they got hidden.

Investigation against code (not against draft text) confirmed every claim. Spot-checks:
- D1: [datasets/data/entities/parties.csv](../../../datasets/data/entities/parties.csv) col 11 blank for 952 rows.
- D3: 4 sites in 2 files; all use `<img src="/icons/landmark.svg">` against stroke-less SVGs; the working `<TopicIcon>` inline-svg path already lives on [frontend/src/lib/parties/RecognitionStrip.svelte](../../../frontend/src/lib/parties/RecognitionStrip.svelte) line 58.
- D9: [frontend/src/lib/sources/SourceList.svelte](../../../frontend/src/lib/sources/SourceList.svelte) is the shared primitive already in use on StateOverview line 1069 + Yenask line 916; party page uniquely uses `PartySourcesStrip` + `PartyCoverageBadge`.
- D11 italic locations: [frontend/src/lib/parties/PartyAllianceContext.svelte](../../../frontend/src/lib/parties/PartyAllianceContext.svelte) line 194; [frontend/src/lib/parties/PartyCurrentStrength.svelte](../../../frontend/src/lib/parties/PartyCurrentStrength.svelte) line 160; the other 2 ("Latest cycle per body..." + "Recorded for N cycles...") originate from [frontend/src/lib/view-models/party-sources.ts](../../../frontend/src/lib/view-models/party-sources.ts) lines 364-376 and render via `PartyCoverageBadge.svelte` - PR-9's retire-on-delete of `PartyCoverageBadge` kills those 2 organically; PR-11 kills the remaining 2.
- D12: [frontend/src/lib/route-crumbs.ts](../../../frontend/src/lib/route-crumbs.ts) line 332 `partyCrumbs()` exists and is wired in [frontend/src/main.ts](../../../frontend/src/main.ts) line 158; [frontend/src/routes/Party.svelte](../../../frontend/src/routes/Party.svelte) never imports or mounts `<Breadcrumb>`. The shared component already implements `sticky top-12 lg:top-0 z-20 bg-white/80 backdrop-blur` (line 56), so D12 is mount + audit, not behaviour invention.

### 0.2 Scope-change ledger

| Row | Date | Intent (what changed, why, what it overrode) | signoff |
| --- | --- | --- | --- |
| L-1 | 2026-06-15 | The data-quality doctrine at [docs/concepts/data-quality.md](../../concepts/data-quality.md) (`processing_level=minor|major` + `processing_note` paired with `source_id`) is the binding pattern for D1's mixed-source backfill. `source_id` cites the issuing authority for party registration (Election Commission of India); when the data path went through a curator/scraper-style party catalogue website, the row carries `processing_level="major"` + a non-empty `processing_note` recording the discretionary call ("founded_year transcribed from third-party party-catalogue website on 2026-06-15; cross-checked against publisher records where available"). The acquisition site is operational knowledge in the curator's notebook; it is NOT cited on the row, in commit messages, in this plan, or in any docs page minted by D13. This BAKES the L-1 row from the previous draft (which left mixed-source backfill acceptance pending) and removes any silent demotion concern - the right doctrinal primitive already exists. | baked - cites [docs/concepts/data-quality.md](../../concepts/data-quality.md) per-row processing-level vocabulary. |
| L-2 | 2026-06-15 | PR-7 verdict (retire `StrongholdDotStrip`, adopt the one-line tally `State - Constituency - won N of M times, last YYYY`) is BAKED FROM FIRST PRINCIPLES, not from any external benchmark. Jony + Citizen converged: the citizen-readable tally vocabulary - state + constituency + lifetime tally + recency in one line - is the deletion-first replacement for the unreadable dot strip; the dot strip carried only tally; the new line carries state + constituency + tally + recency in the same vertical space. No third-party site is cited as authority in the plan-doc body, the Scope ledger, the commit messages, the PR descriptions, the in-code comments, or any docs page minted by D13. The previous draft's L-2 (which named an external third-party party-catalogue benchmark as the design source for the stronghold-row vocabulary) is OVERRIDDEN. | baked - first-principles Jony + Citizen convergence. |
| L-3 | 2026-06-15 | The OWID-aligned source-citation standard at [docs/concepts/data-provenance.md](../../concepts/data-provenance.md) (`dedupeToPills` -> one pill per `(producer x series-family)` with vintage summary, rendered by `<SourceList>`) is already documented and already in use by StateOverview + Yenask. D9 verdict: party page adopts the existing shared `<SourceList>` per card; no view-model widening beyond `dedupeToPills(cardSourceRows)`; no extension of source.csv columns; no per-card-pill-array invention. The previous draft's reader-before-writer split (PR-9a VM widen, PR-9b render swap) is overridden by section 0.5 RIP AND REPLACE doctrine - the writer surface is one line per card so the contract surface is local; collapse to one PR. Default verdict to bake on the `(producer x series-family)` bucketing question: ONE pill PER CARD (per the StateOverview pattern), max 3 pills inline with `+N more` overflow per the existing `SourceList.svelte` `max_inline=3` default. | baked - cites [docs/concepts/data-provenance.md](../../concepts/data-provenance.md) inline ADR `citation-ledger-5col` + `dedupeToPills`. |

### 0.3 ESCALATE triggers (Level-5 - STOP for user sign-off)

- **E1 (D7 PageContainer cap)**: If Jony + Gregor in debate cannot converge on ONE shared cap value for the `<PageContainer>` primitive (bracket: `max-w-screen-2xl` 1536px vs `max-w-7xl` 1280px vs unbounded `min(100%, 1536px)` token), STOP. Decision lands on the design-system spine, not the orchestrator's call.
- **E2 (D8b delim-existence gate)**: If the lifetime stronghold list carries PCs whose `entity_id` belongs to a pre-2024 delimitation that has no matching boundary in `datasets/data/entities/electoral.csv` for the latest `general-2024` event, the row cannot link safely. Default disposition: "link only when delim=current matches; else render plain text". If the crosswalk needs to exceed a one-shot lookup against the canonical entity tier, STOP - that becomes a Level-5 multi-delim canonical fold (Hans + Max).
- **E3 (D9 source-citation schema bump)**: If Max + Hans propose extending [datasets/data/entities/source.csv](../../../datasets/data/entities/source.csv) beyond its current 5 columns to carry OWID-style methodology / processing / license fields, STOP. The 5-col contract was locked 2026-06-11 via inline ADR `citation-ledger-5col` in [docs/concepts/data-provenance.md](../../concepts/data-provenance.md). Re-opening it is Level-5. D9 is rendering-only; methodology surfacing belongs in `AboutThisData.svelte` (concept-state per page).
- **E4 (D11 alliance time-cap value)**: If Jony + Citizen cannot converge on ONE cap rule (bracket: last 10 years vs last 2 cycles per body vs last election only), STOP. Default verdict to bake: "latest cycle per body, only if event_year >= currentYear - 10". If this still surfaces >8 jurisdictions for a major party (BJP / INC), tighten to "latest cycle per body, only if event_year >= currentYear - 6" (one full Lok Sabha + one full Rajya Sabha cycle).
- **E5 (D12 sticky audit fan-out)**: If the global breadcrumb audit reveals >3 routes with bespoke (non-shared) breadcrumb implementations, STOP. The default disposition (mount `<Breadcrumb>` on Party.svelte + verify shared adoption on the other ~25 routes) becomes a Level-3 unification migration that warrants its own plan-doc.
- **E6 (any persona convergence loss)**: If a per-row persona debate hits depth 3 without convergence, STOP per EXECUTION BLOCK rule 8.

### 0.4 Doctrine locks (read these before each row)

- **Authority assignment** (CLAUDE.md section 0a):
  - D1 = Hans + Max (data shape + processing-level doctrine).
  - D2 / D5 / D8a / D8c / D10 / D11 = Jony + Citizen.
  - D3 / D4 / D6 = Jony + Fowler.
  - D7 / D12 = Jony + Gregor (cross-cutting layout discipline).
  - D9 = Hans + Max + Jony (contract + render).
  - D13 = Jony + Citizen (copy doctrine) + the docs author.
- **One Rule** (CLAUDE.md section 0a): OWID is the canonical reference for source citation. D9 verdict adopts the OWID `origin.*` triple verbatim via the existing 5-col `source.csv` shape; rendering follows the OWID inline-publisher-pill pattern via the existing shared `<SourceList>`.
- **Holy Law #5** (CLAUDE.md): structural fixes only. D3 is `<img>` -> `<TopicIcon>` (structural); D7 is shared-primitive (structural); D12 is shared-primitive (structural). No band-aided `font-size` tweaks.
- **Holy Law #9** (CLAUDE.md): every observation row carries `source_id`. D1 backfill rows ship with `source_id` populated (Election Commission of India for party registrations) + `processing_level` + `processing_note` per L-1 doctrine.
- **CLAUDE.md section 10 STOP-AND-SURFACE**: the L-1 / L-2 / L-3 ledger rows are the surfaced intents; do not silently demote at execution time. No third-party party-catalogue site name appears in any committed artifact (plan / docs / commit / PR / in-code comment) per L-2.
- **Jony reductionism**: every fix earns its place by surviving deletion. D5 retire-dot-strip + D8c remove-thumbnail-and-file + D9 retire-strip-and-coverage-badge + D11 kill-4-italics are deletion-first; D2 add-symbol + D3 fix-icon + D4 add-W-logo + D10 skip+rotate + D12 mount-breadcrumb + D13 mint-docs-page are additions that survive because the citizen needs the signal they carry.
- **Defaults are the product**: D7 picks one cap for everyone; D12 sets one sticky-breadcrumb pattern for everyone; D11 picks one time-cap for everyone.

### 0.5 RIP AND REPLACE doctrine (no strangler fig)

Deletions happen IN THE SAME PR as their replacements. NO v1/v2 parallel surfaces. NO "deprecated for one PR, deleted in the next" choreography. Git is the safety net if something needs reversing. The previous draft's PR-9a / PR-9b reader-before-writer split is the exact pattern this overrides - collapse to one PR-9. The previous draft's "`PartyStrongholdMap.svelte` stays in the repo as dead-code-with-context" sentence is the exact pattern this overrides - PR-8a deletes both the mount AND the component file in the same PR.

Per-PR applicability:
- PR-7 deletes `StrongholdDotStrip.svelte` + its test in the same PR as the row reshape.
- PR-8a deletes `PartyStrongholdMap.svelte` + its test in the same PR as the mount removal.
- PR-9 deletes `PartySourcesStrip.svelte` + `PartyCoverageBadge.svelte` + the `PartyCoverageBadgeText` + `PartySourcesStrip` interfaces in the same PR as the `<SourceList>` adoption.
- PR-11 deletes the 2 surviving italic-caveat blocks in `PartyAllianceContext.svelte` + `PartyCurrentStrength.svelte` in the same PR as the time-cap (the other 2 italics retire organically with PR-9's `PartyCoverageBadge` delete).
- PR-13 mints the docs page + adds the "About this page ->" link in the same PR (no dark-shipped docs page sitting orphan).

CARVE-OUT: schema-versioning changes (writer-strict / reader-compatible per CLAUDE.md section 11) still follow reader-before-writer because that's a separate contract obligation. The RIP doctrine here governs FRONTEND COMPONENT replacements + DATA REWRITES where git is the backup.

## Section 1 - Status Reckoner

| Row | Title | Status | PR | Effort |
| --- | --- | --- | --- | --- |
| PR-1  | D1 founded_year backfill (ECI source + processing_level=major per L-1)                                                       | [x] MERGED    | #1046                                                                              | M  |
| PR-2  | D3 empty-square icon fix: inline `<TopicIcon>` swap (4 sites, 2 files)                                                        | [x] MERGED    | #1040                                                                              | S  |
| PR-3  | D4 wikipedia.svg asset add + `PartyAboutCard` "W" logo render                                                                 | [x] MERGED    | #1043                                                                              | S  |
| PR-4  | D6 DualAxisBarLine composite-mode y-axis `0.0%` baseline overlap                                                              | [x] MERGED    | #1035                                                                              | S  |
| PR-5  | D2 recognition strip: inline party-symbol image + text                                                                        | [x] MERGED    | #1042                                                                              | S  |
| PR-6  | D7 `<PageContainer>` primitive + cross-route migration + bare-`max-w-*` contract test                                         | [x] MERGED    | #1051                                                                              | L  |
| PR-7  | D5 strongholds list redesign: retire+DELETE dot-strip, adopt one-line tally                                                   | [x] MERGED    | #1052                                                                              | M  |
| PR-8a | D8c remove the 320x360 `PartyStrongholdMap` thumbnail AND delete the component file                                           | [x] MERGED    | #1053                                                                              | S  |
| PR-8b | D8a `link.pc()` builder + clickable stronghold rows w/ delim-existence gate                                                   | [x] MERGED    | #1054                                                                              | M  |
| PR-9  | D9 render swap (single PR per RIP doctrine): drop `PartySourcesStrip` + `PartyCoverageBadge` + adopt shared `<SourceList>`    | [x] MERGED    | #1056                                                                              | M  |
| PR-10 | D10 immediate: chart x-axis skip+rotate fix on `DualAxisBarLine` / vote-share trend                                           | [x] MERGED    | #1036                                                                              | S  |
| PR-11 | D11 alliance time-cap + DELETE 2 surviving italic in-page disclaimers                                                         | [x] MERGED    | #1059                                                                              | M  |
| PR-12 | D12 global sticky-breadcrumb: mount `<Breadcrumb>` on Party.svelte + audit shared adoption + unify any bespoke holdouts       | [x] MERGED    | #1047                                                                              | M  |
| PR-13 | D13 mint `docs/concepts/party-page-coverage.md` + add "About this page ->" footer link                                        | [x] MERGED    | #1057                                                                              | S  |
| PR-14 | D10 future-proof (Level-3): time-axis range-brush primitive for vote-share trend + future wide-corpus charts                  | [x] COLLAPSED | receipt: [PR14-range-brush-collapse-receipt.md](./20260615-PR14-range-brush-collapse-receipt.md) | L  |
| PR-15 | Closure: archive plan-doc per [docs/how-to/distill-a-plan.md](../../how-to/distill-a-plan.md)                                 | [x] MERGED    | this PR                                                                            | XS |

### Dependency graph

- **Wave A (parallel; data-tier + isolated chart fixes + Level-3 primitive)**: PR-1, PR-4, PR-10, PR-14. All file-disjoint from Party.svelte.
- **Wave B (parallel; party-page leaf components, no `<main>` shell)**: PR-2, PR-3, PR-5.
- **Wave C (global breadcrumb + docs landing site, sequenced BEFORE any per-route migration touching top-of-page region per user requirement)**: PR-12. PR-12 only mounts `<Breadcrumb>` outside the `<main>` wrapper + audits other routes; does not collide with PR-6 or Wave E.
- **Wave D (cross-cutting cap migration, sequence after PR-12 so PR-12 is canonical first)**: PR-6.
- **Wave E (sequential against Party.svelte)**: PR-7 (retire+delete dot strip) -> PR-8a (remove+delete map thumbnail) -> PR-8b (clickable rows) -> PR-9 (sources swap + per-card SourceList; deletes 2 of 4 italics via PartyCoverageBadge retire) -> PR-13 (mint docs page + footer link; lifts the meta-disclaimer copy into the docs page) -> PR-11 (DELETE the 2 surviving italic disclaimers + apply alliance time-cap).
- **Closure**: PR-15 after every other row is DONE or COLLAPSED.

Why PR-13 before PR-11 in Wave E: PR-11 deletes the inline meta-disclaimer text; PR-13 establishes the docs page that holds the replacement narrative. The reader (docs page + footer link) lands first; the writer (italic deletes) lands second. RIP doctrine carve-out: this is a content migration; the docs page IS the replacement surface, not a parallel surface.

## Section 2 - Per-row spec

### PR-1 - D1: founded_year backfill (ECI source + processing_level=major)

**Authority**: Hans + Max (data shape + processing-level doctrine).

**Scope-change ledger row**: L-1 (above). Doctrine cite: [docs/concepts/data-quality.md](../../concepts/data-quality.md) per-row processing-level vocabulary.

**Scope**: Backfill the `founded_year` column on [datasets/data/entities/parties.csv](../../../datasets/data/entities/parties.csv) for the 952 rows currently null. Each row ships with:
- `source_id` -> the existing ECI row in [datasets/data/entities/source.csv](../../../datasets/data/entities/source.csv) where `producer = "Election Commission of India"` (Election Commission is the issuing authority for party registrations in India; the One Rule + Holy Law #9).
- `processing_level = "major"` (for any row whose data path went through a third-party curator/scraper website rather than direct ECI transcription).
- `processing_note` non-empty, e.g. `"founded_year transcribed from third-party party-catalogue website on 2026-06-15; cross-checked against publisher records where available"`. Citizen-readable; no third-party-site name (per L-2 doctrine extending to L-1 prose).
- For the small subset where the founding year IS directly transcribed from ECI's own published register (no third-party hop), `processing_level = "minor"` + empty `processing_note`.

**Priority order** (citizen-visible benefit first):
1. The 3 national parties missing year (BSP, CPI(M), NPP).
2. The 11 state-recognised parties missing year (AJSU, BOPF, MGP, NPF, RSP, TMP, ZPM, AC, KNA, NPEP, TEC).
3. The long-tail of 938 unrecognised-registered parties.

**Files touched**:
- [datasets/data/entities/parties.csv](../../../datasets/data/entities/parties.csv) - column `founded_year` + `source_id` + `processing_level` + `processing_note` filled for as many of the 952 null rows as the curator covers. Surgical inserts only - no full file re-sort (user-memory note from PR #1001).
- [datasets/data/entities/source.csv](../../../datasets/data/entities/source.csv) - 0 new rows expected (existing ECI rows cover party registrations).
- One operator script in `tools/` (one-shot, gitignored output; diff is the artifact). The script body does NOT mention the third-party acquisition site.
- `datasets/data/marts/party_pages/manifest.csv` regenerated via `python -m yen_gov derive-party-pages --root .` (user-memory note from PR #1001).

**Acceptance gates**:
- Tier-A + Tier-B validators exit 0.
- `git diff --stat datasets/data/entities/parties.csv` shows EXACTLY N row-modifications for N backfilled rows (no over-sort artefact).
- pytest backend full suite green.
- Pre-flight baseline captured (`python -c "import csv; print(sum(1 for r in csv.DictReader(open('datasets/data/entities/parties.csv')) if not r['founded_year']))"`); post-PR delta matches the diff.

**Oracle**: For 10 hand-picked anchor parties (INC, BJP, AAP, CPI(M), CPI, DMK, AIADMK, BSP, SP, TMC), the backfilled year MUST equal the publicly-known founding year cross-checked against the ECI public register; AND every backfilled row with `processing_level="major"` carries a non-empty `processing_note`; AND every row's `source_id` resolves to a row in source.csv with `producer="Election Commission of India"`.

**Persona-debate verdict baked (Hans + Max)**: `source_id` carries the issuing authority (ECI for party registrations); `processing_level` + `processing_note` carry the operational receipt for the discretionary call. The per-row scope is the existing yen-gov-native divergence #6 from OWID (per-row instead of per-variable), already locked. No new vocabulary, no new schema fields.

**Browser smoke (section 13)**: Open `/parties/bjp`, `/parties/inc`, `/parties/aap`, `/parties/cpi-m`; confirm the founded-year line under the H1 reads "Founded YYYY" instead of empty.

### PR-2 - D3: empty-square icon fix

**Authority**: Jony + Fowler.

**Scope**: Replace 4 `<img src="/icons/landmark.svg">` / `<img src="/icons/flag.svg">` sites with `<TopicIcon name="landmark">` / `<TopicIcon name="flag">`. Root cause: stroke-less + fill-less Lucide-style SVGs need `currentColor`, which `<img>` cannot inherit; only inline-svg-injection via `<TopicIcon>` works. The pattern already lives correctly on `RecognitionStrip.svelte` line 58.

**Files touched**:
- [frontend/src/lib/parties/PartyCurrentStrength.svelte](../../../frontend/src/lib/parties/PartyCurrentStrength.svelte) lines 111 + 133.
- [frontend/src/lib/parties/PartyAllianceContext.svelte](../../../frontend/src/lib/parties/PartyAllianceContext.svelte) lines 139 + 165.
- One vitest pin asserting the rendered DOM carries `<svg>` (TopicIcon injection), not `<img>`.

**Acceptance gates**: svelte-check, vitest, frontend build, section 13 smoke on `/parties/bjp` confirms landmark + flag glyphs render (not empty squares).

**Oracle**: section 13 browser - `document.querySelectorAll('[data-testid="party-current-strength"] svg').length >= 2` AND `document.querySelectorAll('[data-testid="party-alliance-context"] svg').length >= 2`.

### PR-3 - D4: Wikipedia "W" logo

**Authority**: Jony.

**Scope**: Mint [frontend/public/icons/wikipedia.svg](../../../frontend/public/icons/wikipedia.svg) (Wikipedia "W" wordmark with attribution in [frontend/public/icons/LICENCES.md](../../../frontend/public/icons/LICENCES.md)). Register in [frontend/src/lib/TopicIcon.svelte](../../../frontend/src/lib/TopicIcon.svelte). Render via `<TopicIcon name="wikipedia">` next to the "Wikipedia" link text in `PartyAboutCard.svelte`. Text label SURVIVES (icon is reinforcement, not replacement).

**Audit**: Grep `frontend/src/**` for other Wikipedia link surfaces (`href="https://en.wikipedia.org/"`). If <=3 sites, add the icon there in the same PR. If >3 sites, defer to a separate Level-2 cross-app sweep and confine this PR to the party-page surface.

**Acceptance gates**: svelte-check, vitest, section 13 smoke on `/parties/bjp` confirms the "W" logo renders next to "Wikipedia".

**Oracle**: section 13 - the rendered Wikipedia link contains an `<svg>` icon + text "Wikipedia" + the `href` resolves with HTTP 200.

### PR-4 - D6: DualAxisBarLine 0.0% overlap

**Authority**: Jony + Fowler.

**Scope**: In [frontend/src/lib/charts/DualAxisBarLine/DualAxisBarLine.svelte](../../../frontend/src/lib/charts/DualAxisBarLine/DualAxisBarLine.svelte), suppress the y-axis label at `t === 0` for both `LEFT_TICKS` and `RIGHT_TICKS`. The gridline still anchors the chart; the redundant `"0.0%"` text retires (the x-axis IS the zero line; rendering "0.0%" is chrome).

**Files touched**:
- [frontend/src/lib/charts/DualAxisBarLine/DualAxisBarLine.svelte](../../../frontend/src/lib/charts/DualAxisBarLine/DualAxisBarLine.svelte) - one-line guard `{#if t > 0}<text ...>{bar_format(t)}</text>{/if}` for LEFT, mirror for RIGHT.
- vitest snapshot pin: the DOM no longer contains a `<text>` node with `"0.0%"` text at the baseline `y` coordinate.

**Acceptance gates**: vitest, svelte-check, section 13 smoke on `/parties/bjp` (Parliament chart composite mode) confirms no overlap.

**Oracle**: section 13 - `Array.from(document.querySelectorAll('text')).some(n => n.textContent === '0.0%')` returns `false`.

### PR-5 - D2: recognition strip with inline party symbol

**Authority**: Jony.

**Scope**: The recognition strip currently renders only `recognitionLabel(meta.recognition_scope)` as text. Render the ECI party-symbol image (col 6 `symbol_asset` on parties.csv, already resolved by `getAvatarStyle()`) INLINE inside the pill BEFORE the text. Symbol images are real bitmaps on transparent (not Lucide-style `currentColor` SVGs), so `<img>` renders them correctly (D3 trap does not apply).

**Files touched**:
- [frontend/src/lib/parties/RecognitionStrip.svelte](../../../frontend/src/lib/parties/RecognitionStrip.svelte) - new prop `symbol_url: string | null`; render `<img src={symbol_url} alt="" class="w-4 h-4 inline-block mr-1.5 align-middle">` before text when non-null. Fall back to `<TopicIcon name="info">` when null (sentinel / no symbol).
- [frontend/src/routes/Party.svelte](../../../frontend/src/routes/Party.svelte) ~line 485 - pass `symbol_url={avatar.symbol_url}`.

**Acceptance gates**: svelte-check, vitest pin for the symbol-image branch, section 13 smoke on `/parties/bjp` + `/parties/inc` + `/parties/independent` (sentinel - no symbol; info-icon fallback).

**Oracle**: section 13 - `document.querySelector('[data-testid="party-recognition-strip"] img')` returns non-null on `/parties/bjp`; returns null on `/parties/independent`.

### PR-6 - D7: `<PageContainer>` primitive + cross-route migration

**Authority**: Jony + Gregor. Level-4.

**ESCALATE trigger E1** (section 0.3): if Jony + Gregor cannot converge on ONE cap, STOP.

**Default verdict (pre-debate anchor)**: One primitive at `frontend/src/lib/layout/PageContainer.svelte` with prop `width: "narrow" | "wide" | "full"` defaulting to `"wide"`. Mapping:
- `narrow` -> `max-w-3xl` (~768px): About / Disclaimer / CountingMethodDoc / Settings / NotFound / IndicatorDoc.
- `wide` -> `max-w-screen-2xl` (~1536px): all data-dense surfaces (Home, StateOverview, Explore, Party, TopicLanding, TopicIndex, StateTopic, NationalElection, StateElection, Psephlab, CompareElections, CompareIndicator, DataCompleteness, PartiesIndex, ElectionsFirehose, Constituency, DevChartsSandbox, Yenask).
- `full` -> no cap (Yenask answer-stream if needed).

All variants apply `mx-auto p-4 sm:p-6 space-y-6` so the 5 currently left-aligned routes (TopicLanding / TopicIndex / StateTopic / IndicatorDoc / CompareIndicator) become center-aligned - itself a citizen-visible fix.

**Files touched**:
- New: `frontend/src/lib/layout/PageContainer.svelte` (~30 LOC).
- New contract test: `frontend/src/contracts/no-route-bare-width-cap.test.ts` - greps every `frontend/src/routes/*.svelte` for `max-w-\d` or `max-w-screen-\w+` on a `<main>` or top-level `<section>`; every match must be INSIDE a `<PageContainer>` wrap. Allowlist: NotFound's inline 404 surface inside StateOverview MAY keep `max-w-md` (recovery surface within a wider page).
- Migrate ~22 routes: replace `<main class="max-w-* mx-auto p-* space-y-*">...</main>` with `<PageContainer width="wide|narrow">...</PageContainer>`.

**Acceptance gates**: svelte-check, vitest, new contract test green, section 13 smoke on 4 routes covering both widths.

**Oracle**: New contract test exits 0. Per-route DOM snapshot shows only the outermost `<main>` -> `<main>` shape parity.

**Persona-debate verdict baked**: shared primitive + ONE wide cap + ONE narrow opt-in. README in `frontend/src/lib/layout/` documents the `width` enum.

### PR-7 - D5: strongholds list redesign (retire + DELETE dot-strip, one-line tally)

**Authority**: Jony + Citizen.

**Scope-change ledger row**: L-2 (above). Verdict baked from first principles; no external benchmark cited.

**Scope**: DELETE [frontend/src/lib/parties/StrongholdDotStrip.svelte](../../../frontend/src/lib/parties/StrongholdDotStrip.svelte) entirely (same PR as the row reshape per section 0.5 RIP doctrine). Replace each row's "Sangrur" + dot strip with:

`Punjab - Sangrur: won 3 of 4 times, last 2024`

The line carries 4 pieces of info: state context, constituency, lifetime win-tally, recency. The dot strip carried only tally; the new line carries all four in the same vertical space.

**Files touched**:
- DELETE: [frontend/src/lib/parties/StrongholdDotStrip.svelte](../../../frontend/src/lib/parties/StrongholdDotStrip.svelte) (~120 LOC).
- DELETE: [frontend/src/lib/parties/StrongholdDotStrip.test.ts](../../../frontend/src/lib/parties/StrongholdDotStrip.test.ts).
- [frontend/src/routes/Party.svelte](../../../frontend/src/routes/Party.svelte) ~lines 600-680 - replace per-row dot-strip mount with the new text format. Drop the `import StrongholdDotStrip from ...` line.
- View-model adjustment: widen `PartyStronghold` in [frontend/src/lib/view-models/party-detail.ts](../../../frontend/src/lib/view-models/party-detail.ts) to carry `last_won_year: number | null` if absent.
- pin: vitest for the new row format string.

**Persona-debate verdict baked (Jony + Citizen)**:
- Citizen: the dot strip is not parseable without a legend; the one-line tally is.
- Jony: deletion-first - the dot strip survives only if it does something the text cannot. It does not; delete the component AND the test in the same PR.
- Verdict: text format wins; dot strip retires AND the file goes (RIP doctrine).

**Acceptance gates**: svelte-check, vitest, section 13 smoke on `/parties/bjp` + `/parties/sad` (Punjab focus).

**Oracle**: section 13 - on `/parties/bjp` the first stronghold row's textContent matches `/^[A-Z][a-z ]+ - [A-Z][a-zA-Z- ]+: won \d+ of \d+ times, last \d{4}$/`. Zero dot-strip SVGs in the DOM. `grep -r "StrongholdDotStrip" frontend/src` returns zero matches.

### PR-8a - D8c: remove + DELETE PartyStrongholdMap

**Authority**: Jony reductionism.

**Scope (RIP doctrine - section 0.5)**: Delete BOTH the `<PartyStrongholdMap>` mount in Party.svelte AND the component file in the same PR. The PR-7 row list with state-prefix carries the geographic signal textually. If a richer interactive map is needed later, mint it fresh from `GeoChoropleth` in a separate plan-doc (git is the backup).

**Files touched**:
- [frontend/src/routes/Party.svelte](../../../frontend/src/routes/Party.svelte) - delete the `<PartyStrongholdMap ...>` mount + its import.
- DELETE: [frontend/src/lib/parties/PartyStrongholdMap.svelte](../../../frontend/src/lib/parties/PartyStrongholdMap.svelte).
- DELETE: any vitest pinning `PartyStrongholdMap`.
- [frontend/src/routes/Party.test.ts](../../../frontend/src/routes/Party.test.ts) - drop any assertion that depends on the thumbnail.

**Persona-debate verdict baked (Jony + Gregor + Citizen)**:
- Option A (remove + delete - Jony): the thumbnail is unreadable at 320x360; the row list with state prefix carries the same info textually. RIP the file in the same PR.
- Option B (scale up - Gregor): a full-width 800x600 choropleth would be readable but requires extending GeoChoropleth with palette extensibility. Out of scope; defer.
- Option C (replace with click-through - Citizen): PR-8b makes the row list clickable - this IS the click-through.
- Convergence: REMOVE + DELETE for now (RIP). Re-mint fresh if/when the wider interactive case lands.

**Acceptance gates**: svelte-check, vitest, section 13 smoke confirms the thumbnail is gone and the row list now occupies the same vertical space.

**Oracle**: section 13 - `document.querySelector('[data-testid="party-pc-stronghold-map"]')` returns null; `grep -r "PartyStrongholdMap" frontend/src` returns zero matches.

### PR-8b - D8a: `link.pc()` builder + clickable stronghold rows + delim-existence gate

**Authority**: Jony + Gregor.

**ESCALATE trigger E2** (section 0.3): if the delim-existence check exceeds an `entities/electoral.csv` lookup, STOP.

**Scope**: Add `link.pc(stateCodeOrSlug, eventId, pcSlug)` to [frontend/src/lib/links.ts](../../../frontend/src/lib/links.ts) emitting `/<state>/elections/<event>/<pc-slug>` (the existing Constituency.svelte shape #3). Wrap each PR-7 row in `<a>` if linked target exists; else plain `<span>`:
- VS rows: `link.ac(state_code, ac_name, "assembly-<latest-year-for-state>")` when `(state, ac_name)` matches a row in the canonical entity tier.
- LS rows: `link.pc(state_code, "general-<latest-year>", pc_slug)` when `(state, pc_slug)` matches the latest-delim PC.

Delim-existence gate consumes the canonical entity tier (already loaded via the resolver chain in `party-detail.ts`); no new DuckDB query.

**Files touched**:
- [frontend/src/lib/links.ts](../../../frontend/src/lib/links.ts) - add `link.pc()` (~10 LOC; mirror `link.ac()`).
- [frontend/src/routes/Party.svelte](../../../frontend/src/routes/Party.svelte) - per-row conditional wrap.
- VM: add per-row `pc_slug: string | null` + `href: string | null` so conditional logic lives in TS.
- vitest contract `links.test.ts` adds `link.pc()` case mirroring `link.ac()`.

**Acceptance gates**: svelte-check, vitest, section 13 smoke on `/parties/bjp` clicks one VS row + one LS row; both lead to non-404 pages.

**Oracle**: section 13 - on `/parties/bjp`, the first clickable LS stronghold row's `href` matches `/^\/[a-z-]+\/elections\/general-\d{4}\/[a-z0-9-]+$/`; clicking lands on a Constituency.svelte route with H1 matching the constituency name.

### PR-9 - D9: render swap (single PR per RIP doctrine)

**Authority**: Hans + Max + Jony.

**Scope-change ledger row**: L-3 (above). Doctrine cite: [docs/concepts/data-provenance.md](../../concepts/data-provenance.md) inline ADR `citation-ledger-5col` + `dedupeToPills`.

**ESCALATE trigger E3** (section 0.3): no source.csv schema bump in this PR.

**RIP doctrine note**: The previous draft's PR-9a (VM widen, additive) + PR-9b (render swap, delete) split is OVERRIDDEN by section 0.5. The contract surface is one line per card (`<SourceList pills={dedupeToPills(cardSourceRows)} />`); collapse to one PR. Git is the backup.

**Scope**: In [frontend/src/lib/view-models/party-sources.ts](../../../frontend/src/lib/view-models/party-sources.ts), derive `pills_per_card: Record<CardKey, PublisherPill[]>` via `dedupeToPills(cardSourceRows)` for each of the 5 cards. In [frontend/src/routes/Party.svelte](../../../frontend/src/routes/Party.svelte), replace each `<PartyCoverageBadge text={view_model.provenance.badges.X} />` with `<SourceList pills={view_model.provenance.pills_per_card.X} />`. DELETE the bottom-of-page `<PartySourcesStrip>` mount. DELETE the now-orphan components AND their interfaces in the SAME PR:
- DELETE: [frontend/src/lib/parties/PartyCoverageBadge.svelte](../../../frontend/src/lib/parties/PartyCoverageBadge.svelte).
- DELETE: [frontend/src/lib/parties/PartySourcesStrip.svelte](../../../frontend/src/lib/parties/PartySourcesStrip.svelte).
- DELETE: `PartyCoverageBadgeText` + `PartySourcesStrip` interfaces in `party-sources.ts` (the `pills_per_card` field survives).
- DELETE: every vitest referencing the deleted components.

The "Latest cycle per body..." + "Recorded for N cycles..." italic strings retire ORGANICALLY as a side effect of the `PartyCoverageBadge` delete - 2 of the 4 italics from D11 disappear here; the remaining 2 retire in PR-11.

**Default verdict baked on `(producer x series-family)` bucketing**: ONE pill PER CARD, max 3 inline + `+N more` overflow per the existing `SourceList.svelte` `max_inline=3` default. No callsite override unless a per-card test fails the citizen-readability check at section 13 smoke.

**Files touched** (all in one PR):
- [frontend/src/lib/view-models/party-sources.ts](../../../frontend/src/lib/view-models/party-sources.ts) - add `pills_per_card`; remove `PartyCoverageBadgeText` + `PartySourcesStrip` interfaces.
- [frontend/src/lib/view-models/party-detail.ts](../../../frontend/src/lib/view-models/party-detail.ts) - re-export `view_model.provenance.pills_per_card`.
- [frontend/src/routes/Party.svelte](../../../frontend/src/routes/Party.svelte) - 5 badge swap + 1 strip delete.
- DELETE: [frontend/src/lib/parties/PartyCoverageBadge.svelte](../../../frontend/src/lib/parties/PartyCoverageBadge.svelte) + its test.
- DELETE: [frontend/src/lib/parties/PartySourcesStrip.svelte](../../../frontend/src/lib/parties/PartySourcesStrip.svelte) + its test.
- Extend [frontend/src/contracts/party-page-provenance.test.ts](../../../frontend/src/contracts/party-page-provenance.test.ts) to assert `pills_per_card.<card>.length > 0` for BJP / INC / AAP across all 5 cards; drop assertions on the deleted interfaces.

**Acceptance gates**: svelte-check, vitest, section 13 smoke on `/parties/bjp` confirms each card has a `Source: <publisher> (vintage) ...` line matching the StateOverview pattern; the bottom-of-page 264-row table is gone.

**Oracle**: section 13 - `document.querySelector('[data-testid="party-sources-strip"]')` returns null; each of the 5 cards has a `<p>` matching `/^Source: /` immediately below it. `grep -r "PartyCoverageBadge\|PartySourcesStrip" frontend/src` returns zero matches.

**Persona-debate verdict baked (Hans + Max + Jony)**:
- Hans + Max: source.csv schema stays at 5 cols; OWID methodology/license surfacing is concept-state (per page) not row-state (per source). Defer to `AboutThisData.svelte` in a future plan.
- Jony: shared `<SourceList>` IS the design-system primitive; party page comes into family. Bottom-of-page 264-row table was a one-off invention; deletion-first.
- RIP: shipped in one PR; git is the safety net.

### PR-10 - D10 immediate: chart x-axis skip + rotate

**Authority**: Jony + Citizen.

**Scope**: The vote-share trend chart x-axis collides into `19657389...` because every year-cycle renders as a label. Two-fix immediate (Level-1):
- (a) Angled labels at ~-45deg (CSS `transform: rotate(-45deg); text-anchor: end;`).
- (c) Skip values: render every Nth tick where `N = max(1, ceil(totalTicks / maxTicksThatFit))`; `maxTicksThatFit = floor(chartWidth / minLabelSpacingPx)` with `minLabelSpacingPx = 48`.

The width-cap fix from PR-6 helps (more horizontal room -> more `maxTicksThatFit`); skip + rotate is the actual fix. (b) vertical labels rejected - harder to scan; (d) PR-6 alone insufficient; (e) range-brush deferred to PR-14.

**Files touched**:
- The chart component(s) rendering the "every election contested" vote-share trend on `/parties/<slug>`. Likely [frontend/src/lib/charts/DualAxisBarLine/DualAxisBarLine.svelte](../../../frontend/src/lib/charts/DualAxisBarLine/DualAxisBarLine.svelte) OR a `PartyVoteShareTrend.svelte` component (subagent confirms location). The x-axis tick generator gets the skip rule + `<text>` gets the rotate.
- pin: vitest asserts at chartWidth=320 (mid-tier mobile), the rendered `<text>` count for x-axis is <= 8; at chartWidth=1280 (desktop wide), <= 24.

**Acceptance gates**: svelte-check, vitest, section 13 smoke on `/parties/bjp` (long history -> stresses the algorithm) at viewport widths 360 / 768 / 1280.

**Oracle**: section 13 at viewport=360 - no two `<text>` nodes on the x-axis have overlapping bounding boxes (`getBoundingClientRect`); each visible year label is unambiguously readable (one 4-digit year, no `19657389...` glyph soup).

**Persona-debate verdict baked (Jony + Citizen)**:
- Citizen: must read the years; collisions destroy the chart's purpose.
- Jony: skip + rotate is the classic OWID time-axis pattern; deletion-first applies to label DENSITY, not label PRESENCE - skip the redundant ones, rotate the remaining for clearance.
- Convergence: (c) + (a) immediate; (e) brush primitive separate (PR-14).

### PR-11 - D11: alliance time-cap + DELETE 2 surviving italic disclaimers

**Authority**: Jony + Citizen.

**ESCALATE trigger E4** (section 0.3): if cap value cannot converge, STOP. Default verdict to bake: `event_year >= currentYear - 10` ("last 10 years per body, latest cycle only"). Tighten to `currentYear - 6` if BJP/INC still surface >8 jurisdictions.

**Scope**:
1. Time-cap the alliance ledger in [frontend/src/lib/view-models/party-alliance-context.ts](../../../frontend/src/lib/view-models/party-alliance-context.ts): after `sorted_states` picks the latest cycle per state, filter out rows whose latest cycle is older than `currentYear - 10`. If the filter empties the list for a major party, the section hides entirely (the view-model returns null when both parliament + state_assemblies are empty - existing behaviour).
2. DELETE the 2 surviving italic in-page disclaimers (the other 2 retire organically with PR-9's `PartyCoverageBadge` delete):
   - [frontend/src/lib/parties/PartyAllianceContext.svelte](../../../frontend/src/lib/parties/PartyAllianceContext.svelte) lines 193-197 (`Alliance ties recorded only for the cycles already ingested...`).
   - [frontend/src/lib/parties/PartyCurrentStrength.svelte](../../../frontend/src/lib/parties/PartyCurrentStrength.svelte) lines 158-163 (`Election-night results - does not track post-election defections...`).
3. PRESERVE the sentinel-line italic in [frontend/src/routes/Party.svelte](../../../frontend/src/routes/Party.svelte) line 544 (`text-xs text-slate-500 italic max-w-prose` for NOTA / UNK placeholder copy) - that italic is warning-grade signal about THIS entity, not meta-coverage duplication; out of D11 scope.

The deleted copy is consolidated into the docs page minted by PR-13 (which lands BEFORE PR-11 in Wave E).

**Files touched**:
- [frontend/src/lib/view-models/party-alliance-context.ts](../../../frontend/src/lib/view-models/party-alliance-context.ts) - add `recencyCapYears` constant (10) + filter in `sorted_states` projection; widen the loader test to cover both paths.
- [frontend/src/lib/parties/PartyAllianceContext.svelte](../../../frontend/src/lib/parties/PartyAllianceContext.svelte) - DELETE the `<p data-testid="party-alliance-context-caveat">` block (lines 193-197).
- [frontend/src/lib/parties/PartyCurrentStrength.svelte](../../../frontend/src/lib/parties/PartyCurrentStrength.svelte) - DELETE the italic caveat block (lines 158-163).
- vitest pin: alliance VM with current_year=2026 filters out rows from <=2015; with current_year=2030 filters out <=2019. Per-row tests for BJP showing post-cap jurisdictions.

**Persona-debate verdict baked (Jony + Citizen)**:
- Citizen: pre-poll alliances from 10+ years ago do not predict current behaviour; the list is noise, not signal.
- Jony: deletion-first - if the row does not currently inform the citizen's question ("who does this party currently ride with?"), it does not belong.
- Convergence: cap at 10 years; tighten on data if needed.

**Acceptance gates**: svelte-check, vitest (alliance VM cap + DOM checks), section 13 smoke on `/parties/bjp`, `/parties/inc`, `/parties/sad` confirms alliance list shows only rows from cycles within the last 10 years + zero italic-caveat paragraphs anywhere on the page (modulo the preserved sentinel-line italic).

**Oracle**: section 13 on `/parties/bjp` - every state-assembly row's `event_label` carries a 4-digit year that is `>= 2016`; the elements `[data-testid="party-alliance-context-caveat"]` returns null AND no `<p>` inside `[data-testid="party-current-strength"]` carries italic styling.

### PR-12 - D12: global sticky-breadcrumb + Party.svelte mount + audit

**Authority**: Jony + Gregor (cross-cutting layout discipline).

**ESCALATE trigger E5** (section 0.3): if >3 routes have bespoke breadcrumb implementations, STOP and surface as its own plan-doc.

**Scope**:
1. Mount `<Breadcrumb {crumbs} />` in [frontend/src/routes/Party.svelte](../../../frontend/src/routes/Party.svelte) outside the `<main>` wrapper (mirrors the pattern in `Constituency.svelte` line 344 + `StateOverview.svelte` line 694 + every other adopted route). The `partyCrumbs` builder is already wired in [frontend/src/main.ts](../../../frontend/src/main.ts) line 158; the mount is the only missing piece. Sticky behaviour comes for free (the shared [frontend/src/lib/Breadcrumb.svelte](../../../frontend/src/lib/Breadcrumb.svelte) line 56 already implements `sticky top-12 lg:top-0 z-20 bg-white/80 backdrop-blur`).
2. Audit every `frontend/src/routes/*.svelte` for bespoke breadcrumb implementations (grep for `<nav aria-label="Breadcrumb"` outside the shared component). For each holdout, replace with `<Breadcrumb {crumbs} />` using `route.crumbs?.(route.params) ?? []`. If a route has no crumb builder in `route-crumbs.ts`, add a minimal one (Home -> Self).
3. Add a contract test `frontend/src/contracts/routes-mount-shared-breadcrumb.test.ts`: every `routes/*.svelte` that the router declares `route.crumbs` for MUST import `Breadcrumb` from `../lib/Breadcrumb.svelte` AND render `<Breadcrumb ` somewhere. Allowlist for routes with intentionally-no-crumbs (e.g. About, Disclaimer, NotFound at root).

**Files touched**:
- [frontend/src/routes/Party.svelte](../../../frontend/src/routes/Party.svelte) - import + mount `<Breadcrumb {crumbs} />`.
- N route files (audit result; expected <= 3 holdouts per E5).
- New: `frontend/src/contracts/routes-mount-shared-breadcrumb.test.ts`.

**Persona-debate verdict baked (Jony + Gregor)**:
- Jony: stick-on-scroll, not float; ONE primitive renders consistently across elections, parties, indicators.
- Gregor: enforce by contract test, not by code review.
- Convergence: shared primitive + contract test catches future drift.

**Acceptance gates**: svelte-check, vitest, new contract test green, section 13 smoke on `/parties/bjp` (must show `Home > Parties > BJP`), `/parties/inc`, `/maharashtra/elections/general-2024` (must still show its existing chain), `/` (suppressed - single-leaf), `/about` (suppressed - single-leaf or no chain).

**Oracle**: section 13 on `/parties/bjp` - `document.querySelector('[data-testid="geo-breadcrumb"]')` returns non-null; the `<ol>` contains 3 `<li>` elements with text `Home`, `Parties`, `BJP` in order; the `Parties` element is an `<a>` with `href="/parties"`. On scroll past the viewport, the `<nav>` stays pinned (`getBoundingClientRect().top === 0` at desktop / `=== 48` at mobile).

### PR-13 - D13: mint docs page + footer "About this page" link

**Authority**: Jony + Citizen + docs author.

**Scope**: Mint ONE docs page that consolidates the 4 italic meta-disclaimers retired by PR-9 (organic - 2 of 4) + PR-11 (explicit - 2 of 4) + the alliance recency-cap rationale + the "what counts as a stronghold" rule. Path: `docs/concepts/party-page-coverage.md` (concept tier per CLAUDE.md section 5; the page explains the CONCEPT of party-page coverage to a citizen, not a how-to). Add ONE quiet link at the bottom of Party.svelte's footer: `<a href="/about/party-page-coverage">About this page -></a>` (or the citizen-facing docs route if one already exists; subagent confirms the route shape). The link sits on its own line in slate-400 text, no italic, no chrome.

**Files touched**:
- New: `docs/concepts/party-page-coverage.md` with H1, `Last Updated: 2026-06-15`, sections:
  - **What you are looking at** (one paragraph: what the page shows for each card).
  - **What we have data for** (the post-PR-11 alliance recency cap; the latest-cycle-per-body rule; the "election-night results, no post-poll defection tracking" caveat; the "cycles ingested vs publisher records on file" caveat).
  - **How sources are cited** (link to [docs/concepts/data-provenance.md](../../concepts/data-provenance.md); brief publisher-pill explainer).
  - **How processing levels work** (link to [docs/concepts/data-quality.md](../../concepts/data-quality.md); brief minor/major explainer).
  - **Why some constituencies link and others do not** (delim-existence gate from PR-8b).
  - **See also** cross-links.
- [frontend/src/routes/Party.svelte](../../../frontend/src/routes/Party.svelte) - one quiet footer link.
- (Optional, if a citizen-facing route to render docs/concepts/ pages does NOT exist) defer to a separate Level-2 plan; the docs page still lands and the footer link points at the in-repo GitHub-rendered URL as fallback.

**Persona-debate verdict baked (Jony + Citizen)**:
- Citizen: a single page I can read once is better than 4 italic sentences I have to read on every visit.
- Jony: deletion-first - the italics retire because the consolidated docs page IS their home; nothing is hidden, the content moves.
- Convergence: ship the docs page + the link in the same PR (no parallel surfaces).

**Acceptance gates**: docs lint (markdown), section 13 smoke on `/parties/bjp` confirms the footer link exists, is text-only (no italic, no chrome), and resolves (in-app route OR GitHub-rendered URL).

**Oracle**: section 13 - `document.querySelector('a[href*="party-page-coverage"]')` returns non-null on `/parties/bjp`, with textContent matching `/About this page/`. The linked URL returns HTTP 200.

### PR-14 - D10 future-proof (Level-3): time-axis range-brush primitive

**Authority**: Jony + Gregor + Fowler. Level-3 (new primitive on the chart layer, designed to lift cleanly into StateOverview / yenask / topic-page charts).

**Scope**: Mint `frontend/src/lib/charts/RangeBrush/RangeBrush.svelte` - a thin d3-brush overlay primitive that emits `(startYear, endYear)` events. Mount as an optional opt-in prop `<DualAxisBarLine ... brush={true}>`. When `brush=true`, the chart renders a small brush track below the x-axis; the citizen drags it to set a window; the main chart re-renders to the window. Default OFF; opt-in on the party-page vote-share trend (and any future chart with >20 years of data).

**Acceptance gates**: svelte-check, vitest pin on the brush primitive in isolation (start/end emits, clamp behaviour, reset gesture), section 13 smoke on `/parties/bjp` exercises the brush.

**Oracle**: section 13 - the brush track exists below the chart; dragging it produces a measurable change in the rendered `<text>` year labels (window narrows -> more ticks fit, label rotation can relax).

**Persona-debate verdict baked (Jony + Gregor + Fowler)**:
- Jony: brush is the inevitable Brichter-style gesture for "I want to look at this range".
- Gregor: thin primitive in `frontend/src/lib/charts/`; opt-in prop; default off (defaults are the product; the citizen on the median page does not need the brush).
- Fowler: structural - the primitive is one component reused across surfaces, not bespoke per-chart logic.

**Note**: PR-14 ships independently of the immediate PR-10 fix. Wave A scheduling. If acceptance gates slip or the d3-brush + Svelte 5 integration surfaces a design call, COLLAPSE this PR with a receipt and re-mint in a dedicated Level-3 plan-doc; the immediate fix (PR-10) is sufficient for the current corpus depth.

### PR-15 - Closure

**Authority**: Orchestrator.

**Scope**: Archive this plan-doc per [docs/how-to/distill-a-plan.md](../../how-to/distill-a-plan.md). Lift durable findings:
- D7 PageContainer primitive -> "Page-width discipline" section in the design-system concept doc.
- D9 verdict (shared `<SourceList>` is the family pattern; per-card `AboutThisData` deferred) -> cross-reference from [docs/concepts/data-provenance.md](../../concepts/data-provenance.md).
- D11 + D13 verdict (italic meta-disclaimers retire to docs/concepts/<page>-coverage.md) -> add a "page-coverage doc minting" sub-section to [docs/concepts/documentation-discipline.md](../../concepts/documentation-discipline.md).
- D12 verdict (shared sticky-breadcrumb mounted on every route with `route.crumbs`) -> cross-reference from the design-system concept doc.
- Lessons -> `/memories/lessons.md`:
  - The `<img src>` vs `<TopicIcon>` doctrine for `currentColor` SVGs (PR-2 / D3).
  - The "doctrine already in docs - read before inventing" rule (L-1 + L-3 baked from existing doctrine, not minted fresh).
  - The "RIP doctrine - delete in same PR, git is backup" doctrine (section 0.5).
  - The "italic meta-disclaimer -> docs/concepts page" copy-discipline pattern (D11 + D13).
- Plan-doc moves to `docs/archive/plans/20260615-party-page-citizen-fixes-plan.md` with per-row distillation back-pointers.

## Execution contract (autonomous - follow blindly, do not re-plan)

When this plan is in context and the instruction is "implement it", execute as the ORCHESTRATOR with NO further questions except at an ESCALATE trigger. There is no processing step after this block - the rules below are the whole instruction set.

1. **Orchestrator + subagent-PR topology.** The main agent owns the Status Reckoner and never lets its own context overflow. Each PR-row is dispatched to a stateless `runSubagent` brief that is self-contained: the row scope, the files, the acceptance gates, and the one oracle. The subagent does the row; the orchestrator merges and moves on.
2. **One row = one PR = one branch.** Park master on a `scratch-master-parking` branch so no worktree owns `main` (clean gh-merge). Author per `docs/how-to/ship-a-pr.md`: 2-commit-then-squash, the 5-gate Definition-of-Done, browser-verify for any frontend/admin runtime change.
3. **Ship loop, non-stop.** Keep PRs in flight; never idle. As soon as one row's gates are green, merge (`gh pr merge --squash --delete-branch`), pull main, start the next row. Pre-existing unrelated test failures are not gating - document the baseline, do not block.
4. **Tests ship with the row.** Write/update only the tests the row needs. Full suite green at merge. No new mocks unless asked.
5. **Persona debate converges to ONE ruling.** When a row hits a contested design call, run the authority personas (CLAUDE.md section 0a) in debate, not parallel review; bake the single written verdict into the row and proceed.
6. **Manage context via offload.** Push breadth-y reads, audits, and exploration into subagents so the orchestrator's window stays lean. The orchestrator holds only the Reckoner, the current row, and the merge state.
7. **Post-merge hygiene every time.** Delete the remote branch, prune `: gone` local branches, remove `.tmp_*`, distill durable lessons.
8. **Stop only at a real boundary.** Stop and ask ONLY when: an ESCALATE trigger fires (Level-5), an explicit user-named source/instruction would be scope-narrowed (STOP-AND-SURFACE per CLAUDE.md section 10), or an audit chain exceeds depth 3 (the loop is lossy - escalate with Path A/B/C options, do not ship a 4th audit). Otherwise do not pause; the user is not watching.
9. **Closure.** Done only when every in-scope row is DONE or COLLAPSED-with-cited-rationale. No-op rows carry a receipt (the command + its zero result). Archive the plan-doc with a per-row distillation map per `docs/how-to/distill-a-plan.md`.

## See also

- [CLAUDE.md](../../../CLAUDE.md) - section 0a authority table, section 6 correction levels, section 10 anti-patterns + STOP-AND-SURFACE, section 5 ASCII discipline, section 11 schema versioning carve-out for the RIP doctrine.
- [docs/concepts/data-provenance.md](../../concepts/data-provenance.md) - inline ADR `citation-ledger-5col` (5-col source.csv contract); `dedupeToPills` doctrine (L-3 + PR-9 cite).
- [docs/concepts/data-quality.md](../../concepts/data-quality.md) - per-row processing-level vocabulary (`minor` / `major` + `processing_note`); L-1 + PR-1 cite.
- [docs/concepts/owid-alignment.md](../../concepts/owid-alignment.md) - OWID `origin.*` triple identity; named divergence #6 (per-row processing scope); the One Rule.
- [docs/concepts/citizen-first.md](../../concepts/citizen-first.md) - persona pipeline.
- [docs/how-to/ship-a-pr.md](../../how-to/ship-a-pr.md) - PR lifecycle the EXECUTION BLOCK references.
- [docs/how-to/distill-a-plan.md](../../how-to/distill-a-plan.md) - closure ritual.
- [docs/how-to/handle-scope-change.md](../../how-to/handle-scope-change.md) - STOP-AND-SURFACE doctrine.
- [docs/archive/plans/20260614-party-page-reimagination-plan.md](../../archive/plans/20260614-party-page-reimagination-plan.md) - predecessor plan; the 13 defects surfaced on its deployed-site review.
- [frontend/src/lib/Breadcrumb.svelte](../../../frontend/src/lib/Breadcrumb.svelte) - shared sticky-breadcrumb primitive (D12 cite).
- [frontend/src/lib/sources/SourceList.svelte](../../../frontend/src/lib/sources/SourceList.svelte) + [frontend/src/lib/sources/format.ts](../../../frontend/src/lib/sources/format.ts) - shared publisher-pill render + `dedupeToPills` projector (D9 cite).
- `/memories/lessons-2026-06-14-party-page-reimagination.md` sections 5 + 6 - forensic capture of "why did the persona debate miss these defects" (the `<img src>` vs `<TopicIcon>` doctrine + the citizen-first persona debate requirement).

## Plan complete

Closed 2026-06-15. 11 rows MERGED + 1 row COLLAPSED + this closure PR (PR-15) shipped per [docs/how-to/distill-a-plan.md](../../how-to/distill-a-plan.md). The 3 rows that landed earlier the same session (PR-2 / PR-4 / PR-10) plus the 11 wave rows (PR-1, PR-3, PR-5, PR-6, PR-7, PR-8a, PR-8b, PR-9, PR-11, PR-12, PR-13) account for the 14 implementation PRs; PR-14 collapsed to a receipt-only deliverable.

Per-row distillation map:

- PR-1 (#1046) - durable doctrine already lives at [docs/concepts/data-quality.md](../../concepts/data-quality.md) (per-row `processing_level` / `processing_note` paired with `source_id`) + [docs/concepts/owid-alignment.md](../../concepts/owid-alignment.md) named divergence #6; per-PR audit trail stays in this plan-doc.
- PR-2 (#1040) + PR-3 (#1043) - `<img src>` vs `<TopicIcon>` doctrine for `currentColor` SVGs lifted to `/memories/lessons-2026-06-15-party-page-citizen-fixes.md`; subsystem doc home for icon registry remains [frontend/src/lib/TopicIcon.svelte](../../../frontend/src/lib/TopicIcon.svelte) (read-the-code, no separate `docs/` page warranted).
- PR-4 (#1035) + PR-10 (#1036) - chart-renderer fixes; per-PR audit trail stays in this plan-doc; closed-renderer extension log at [docs/concepts/schema-is-the-design-system.md](../../concepts/schema-is-the-design-system.md) was already updated by the merged PRs themselves.
- PR-5 (#1042) - per-PR audit trail stays in this plan-doc; rendering rule is a one-line component contract on `RecognitionStrip.svelte`, no doc home needed.
- PR-6 (#1051) - `<PageContainer>` primitive shipped at [frontend/src/lib/layout/PageContainer.svelte](../../../frontend/src/lib/layout/PageContainer.svelte) with its own README; the cross-route contract test at [frontend/src/contracts/no-route-bare-width-cap.test.ts](../../../frontend/src/contracts/no-route-bare-width-cap.test.ts) is the canonical enforcement seam; the "doctrine already in docs - read before inventing" agent-craft lesson lifts to `/memories/lessons-2026-06-15-party-page-citizen-fixes.md`.
- PR-7 (#1052) + PR-8a (#1053) + PR-9 (#1056) + PR-11 (#1059) - RIP doctrine (delete same-PR as replacement; git is the safety net) lifts to `/memories/lessons-2026-06-15-party-page-citizen-fixes.md`; section 0.5 of this plan-doc remains the canonical statement of the doctrine and the carve-out for schema-version reader-before-writer per [CLAUDE.md](../../../CLAUDE.md) section 11.
- PR-8b (#1054) - `link.pc()` builder shipped on [frontend/src/lib/links.ts](../../../frontend/src/lib/links.ts) (its existing test file is the contract surface); delim-existence gate logic lives in [frontend/src/lib/view-models/party-detail.ts](../../../frontend/src/lib/view-models/party-detail.ts).
- PR-9 (#1056) - shared `<SourceList>` adoption pattern is already documented at [docs/concepts/data-provenance.md](../../concepts/data-provenance.md) (`dedupeToPills` doctrine); the `mergeLabelDuplicates` defensive 2nd-pass pattern for Svelte `{#each ... (key)}` collisions lifts to `/memories/lessons-2026-06-15-party-page-citizen-fixes.md`.
- PR-11 (#1059) - VM-layer time-cap with test-injectable `current_year` override pattern lifts to `/memories/lessons-2026-06-15-party-page-citizen-fixes.md`; canonical data stays complete per [CLAUDE.md](../../../CLAUDE.md) section 10 (cap at render, not at source.csv).
- PR-12 (#1047) - sticky-breadcrumb contract test at [frontend/src/contracts/routes-mount-shared-breadcrumb.test.ts](../../../frontend/src/contracts/routes-mount-shared-breadcrumb.test.ts) is the enforcement seam; the shared primitive at [frontend/src/lib/Breadcrumb.svelte](../../../frontend/src/lib/Breadcrumb.svelte) is its own doc-home (read-the-code).
- PR-13 (#1057) - docs page at [docs/concepts/party-page-coverage.md](../../concepts/party-page-coverage.md) is itself the durable artifact; the "italic meta-disclaimer -> docs/concepts page" copy-discipline pattern lifts to `/memories/lessons-2026-06-15-party-page-citizen-fixes.md`.
- PR-14 (COLLAPSED) - receipt at [20260615-PR14-range-brush-collapse-receipt.md](./20260615-PR14-range-brush-collapse-receipt.md) is the durable artifact; recommends Path A (wire existing `TemporalViewportBrush` into `DualAxisBarLine`) as a future Level-2 PR if/when the corpus depth justifies it.
- PR-15 (this PR) - the archive + lessons-lift itself; no follow-on distillation row.

Lessons lifted to `/memories/lessons-2026-06-15-party-page-citizen-fixes.md` (per [CLAUDE.md](../../../CLAUDE.md) section 5: agent-craft execution lessons go to user-memory, not `docs/`):

1. `<img src>` vs `<TopicIcon>` doctrine for `currentColor` SVGs (PR-2 / PR-3 / D3 + D4).
2. "Doctrine already in docs - read before inventing" (PR-6 / PR-9 / PR-14 / D7 + D9 collapse).
3. RIP doctrine: delete-in-same-PR as the replacement (PR-7 / PR-8a / PR-9 / PR-11 / section 0.5).
4. "Italic meta-disclaimer -> docs/concepts page" copy-discipline pattern (PR-11 + PR-13 / D11 + D13).
5. VM-layer time-caps with test-injectable `current_year` override (PR-11 / D10).
6. `mergeLabelDuplicates` 2nd-pass pattern for Svelte `{#each ... (key)}` collisions (PR-9 / D9).

Plan-doc remains as the audit ledger; do not edit further. New work starts a new plan-doc.

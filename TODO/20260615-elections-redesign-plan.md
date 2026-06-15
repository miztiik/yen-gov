# Elections redesign - General elections + Assembly elections

**Last Updated**: 2026-06-15
**Level**: 4 (structural; touches 4+ files across schema + backend writer + frontend routes + curator data + docs)
**Status**: APPROVED (Section 3 sign-off receipts captured 2026-06-15). Executing autonomously per EXECUTION BLOCK.

> Persona debate per CLAUDE.md section 0a (Jony UI -> Hans governance -> Fowler engineering), converged 2026-06-15. Naming and nav decisions (Section 0.1) converged in a second pass (Citizen + Hans + Max + Jony, 2026-06-15). This doc carries its own EXECUTION BLOCK; the executing agent runs rows E1-E5 end-to-end without further dictation.

## Section 0 - Operating contract

### Why this plan exists

The current `/t/elections` page renders **315 election rows** in one sortable table called "Elections firehose". Each row is hydrated on demand via IntersectionObserver + a 4-concurrent promise pool over DuckDB-WASM `read_csv` queries. **Measured on localhost 2026-06-15 via Playwright** (test forces every row to hydrate by scroll-to-bottom): page load ~2.4s, full hydration ~41.4s, doc scroll surface ~14,744 px. On a mid-tier Android over 4G (the Citizen target per CLAUDE.md), this is multiples worse - 313 separate CSV fetches at 30-200KB each, serialised through a 4-wide pool.

Two distinct citizen-questions are conflated on one surface:

- **"How has Parliament voted across cycles?"** - a time-series question, OWID-aligned, well-served by a General-election table (the [indiavotes Parliament page](https://www.indiavotes.com/lok-sabha/) precedent).
- **"Who runs each state right now?"** - a place-first question, well-served by a state-card grid showing latest-only (the [indiavotes state-assembly page](https://www.indiavotes.com/vidhan-sabha/) precedent).

The user named both precedents explicitly. The current firehose answers neither cleanly.

### Hard-coded scope

In scope:

- New `event_summary.csv` aggregate (one row per election event) at `datasets/data/datapoints/electoral/event_summary.csv`
- New backend writer `derive-event-summary` Typer command
- Two new frontend routes - `/t/elections` (General elections) and `/t/elections/assemblies` (Assembly elections) - with a shared `ElectionsRouteTabs` nav strip
- Inline progress-bar indicator for vote-share (pure Tailwind, no new renderer)
- Turnout-delta column with green/red glyph (client-side derived)
- Drop the sr-only "Open" column; year-text becomes the link affordance
- DELETE `frontend/src/routes/ElectionsFirehose.svelte` in the SAME PR as the new routes ship (rip-and-replace; see Section 0.2 doctrine)
- 5-state CM backfill on `datasets/data/datapoints/office_holdings.csv` for Assam / Kerala / Tamil Nadu / West Bengal 2026 incumbents + Puducherry 2021->2026 row split
- Doc updates: `docs/architecture/data/canonical-store.md`, `docs/concepts/office-holders.md`

Out of scope (per Section 3 Q3 sign-off):

- Per-AC drill-down detail pages (`/t/elections/<event-slug>`, `/<state>/elections/<event-slug>`) - they keep loading per-event CSVs via `loadElectionResults()`; only the firehose entry-point changes.
- Per-state hero on `/<state>` (StateOverview.svelte) - retained as-is per user direction.
- `DualAxisBarLine` composite mount on this surface - over-engineering for an inline single-row cell.
- Indicator/topic catalogue changes; election-events.json changes.
- Schema MAJOR bump (event_summary.csv is additive minor: columns.json 2.0 -> 2.1).
- a11y / WCAG / aria-* enforcement at project level (CLAUDE.md section 0 non-goal). The ElectionsRouteTabs ARIA tablist annotations land because they are 4 LOC, not because the project enforces a11y broadly.

### ESCALATE triggers (PAUSE and ask user)

- Any column on `event_summary.csv` would require a MAJOR x-version bump on columns.json (i.e. non-additive). The current design is additive minor.
- The CM backfill for any of the 5 states would require closing a row a curator did not author (i.e. closing an OPEN 2021 row whose holder is a different person than expected). Stop and surface the wiki/web evidence to user for sign-off before mutating office_holdings.csv.
- Per-event drill-down pages regress (`loadElectionResults()` callers break) - rollback rather than band-aid.

All other ambiguities are pre-resolved in this plan-doc (Sections 0.1 naming, 0.2 rip-and-replace, 3 sign-off receipts, 6 persona transcript). The orchestrator does NOT re-ask.

### Chosen strategy (binding)

Two routes serving two distinct citizen questions. Backend emits ONE aggregate CSV. ElectionsRouteTabs shared nav strip is mounted on both routes so the sibling route is always one tap away.

**Mechanism**: Backend emits `datasets/data/datapoints/electoral/event_summary.csv` (one row per `(event_id, state_code)` tuple - 6 General-election rows with `scope=national, state_code=null` + 303 Assembly rows with `scope=state, state_code=<eci>` + complete byes). Frontend loads the single CSV once and composes both routes from it. The 315-row lazy-hydration firehose + IntersectionObserver + promise pool gets DELETED in the same PR that ships the new routes (rip-and-replace per Section 0.2). The inline vote-share indicator is plain Tailwind `div + bg-color + width-pct` (closed-set faithful). The "Open" sr-only column is dropped; the year text becomes the click affordance.

## Section 0.1 - Naming verdict (Citizen + Hans + Max + Jony converged 2026-06-15)

The "Elections firehose" name and the "Lok Sabha" / "Vidhan Sabha" Hindi-script labels are RETIRED per user direction 2026-06-15 ("lets not call it election firehose ... lok sabha or vidha sabha wording no hind just english"). The English-only citizen-chrome policy already in force on this project (per the PR-0 named divergence in [docs/architecture/frontend/url-grammar.md](docs/architecture/frontend/url-grammar.md)) reinforces the same rule.

**Binding name verdict** (do NOT re-litigate):

| Surface                                                  | New copy             | Old copy (retired)                    |
| -------------------------------------------------------- | -------------------- | ------------------------------------- |
| Route `/t/elections` H1 + crumb leaf + tab pill          | **General elections**| "Elections firehose" / "Lok Sabha"    |
| Route `/t/elections/assemblies` H1 + crumb leaf + tab pill | **Assembly elections** | (did not exist) / "Vidhan Sabha"   |
| Shared parent breadcrumb                                 | **Elections**        | (unchanged)                           |

**Binding file-name verdict**:

| Old name                                                    | New name                                                |
| ----------------------------------------------------------- | ------------------------------------------------------- |
| `frontend/src/routes/ElectionsFirehose.svelte`              | DELETED (rip-and-replace)                               |
| (placeholder) `frontend/src/routes/ElectionsTable.svelte`   | `frontend/src/routes/GeneralElections.svelte`           |
| (placeholder) `frontend/src/routes/ElectionsAssemblies.svelte` | `frontend/src/routes/AssemblyElections.svelte`       |
| (none)                                                      | `frontend/src/lib/elections/ElectionsRouteTabs.svelte` (NEW shared nav) |
| (placeholder) `parliament-table-model.ts`                   | `frontend/src/lib/view-models/general-elections-model.ts` |
| (placeholder) `assembly-cards-model.ts`                     | `frontend/src/lib/view-models/assembly-elections-model.ts` |

**Test-id naming convention**: `general-elections-<x>` for the General route, `assembly-elections-<x>` for the Assembly route, `elections-route-tabs` for the shared nav.

**URLs unchanged**: `/t/elections` (General) and `/t/elections/assemblies` (Assembly). The bare URL stays sensible because parliamentary cycles are the spanning context for any "elections in India" link a citizen has bookmarked or shared on WhatsApp. URL asymmetry mirrors the indiavotes precedent the user named.

**Nav glue verdict (Jony D2, ratified by Citizen)**: shared `ElectionsRouteTabs.svelte` top tab strip mounted ABOVE the H1 on both routes. Two pills - "General elections" (linked to `/t/elections`) + "Assembly elections" (linked to `/t/elections/assemblies`). Active pill is filled (`bg-slate-900 text-white`); inactive is outline (`border-slate-300 text-slate-700 hover:bg-slate-100`). The component takes one prop `current: "general" | "assembly"`. Mobile contract: pills stay horizontal; full width row; each pill is `< 50%` width so they never wrap at `< 640px`. ARIA: `role="tablist"` on the container, `role="tab"` on each link, `aria-current="page"` on the active pill. Pattern reuses the existing Tailwind pill family used by the firehose body-filter, ScopePicker, and HomeElectionsRail door - no new chrome.

**Citizen tests passed**:

- 30-year-old in Bengaluru reading English news (`Hindustan Times`, `The Hindu`, indiavotes) types "general elections" or "assembly elections" - the H1 phrasing matches search intent.
- Mobile citizen on bare `/t/elections` sees the General table by default plus an Assembly pill one tap away - discoverable without scrolling.
- WhatsApp-forward of `/t/elections` lands on the most-broadly useful surface (national context) without misleading.

**Hans test passed**: "general election" is Wikipedia's term for India Lok Sabha events; "assembly election" is the constitutionally-honest term for state legislative assembly elections. Neither phrase misleads.

**Max test passed**: English-literal phrasing survives any future regional-script localisation pass.

## Section 0.2 - Rip-and-replace doctrine (user-mandated 2026-06-15)

> Verbatim user direction 2026-06-15: "RIP AND REPLACE - NO STRANGLER FIG. GIT IS BACKUP. NO PRISONERS MOVE FORWARD BOLDLY REIMAGINE."

The PR that ships the new routes (E4) ALSO ships the deletion of the old firehose in the same commit-set. No parallel-surface period. No interim "old route still reachable from /t/elections-old" fallback. No `RedirectLegacyFirehose.svelte` strangler-fig. Git history is the rollback path - if the redesign regresses, `git revert` the merge commit.

This explicitly OVERRIDES the cautious "two-PR ship then delete in E6" sequencing in the persona-1 verdict. The user has authorised boldness. Section 1 Reckoner reflects this (5 rows, not 8).

## Section 1 - Status Reckoner

| Row | Title                                                                       | Status        | PR  | Effort  |
| --- | --------------------------------------------------------------------------- | ------------- | --- | ------- |
| E1  | Lock `event_summary.csv` schema in columns.json (READER-BEFORE-WRITER)      | [ ] PENDING   |     | S       |
| E2  | Backend `event_summary_writer` + Typer CLI + emit + Tier-B receipt          | [ ] PENDING   |     | M       |
| E3  | Frontend `event-summary-loader` + 2 view-models + unit + Tier-A contract     | [ ] PENDING   |     | M       |
| E4  | RIP-AND-REPLACE: 2 routes + nav tabs + delete firehose + home rail copy      | [ ] PENDING   |     | L       |
| E5  | CM backfill: 2026 incumbents for S03 / S11 / S22 / S25 + U07 row-split       | [ ] PENDING   |     | M       |

Effort key: S = single sitting; M = a few hours; L = a day plus.

Hard dependency: E1 -> E2 -> E3 -> E4. E5 is independent (ships any time).

## Section 2 - Per-row spec

### Row E1 - Lock event_summary.csv schema

**Scope**: Append the `event_summary.csv` file-class to `datasets/data/_schema/columns.json` (additive minor; bump `$schema_version` 2.0 -> 2.1; bump `x-version` and add `x-changelog` entry on `columns.schema.json`). No writer ships yet; no data file ships yet. This is the READER-BEFORE-WRITER contract surface.

**Files touched**:

- [datasets/data/_schema/columns.json](datasets/data/_schema/columns.json) - add the file-class block (12 columns)
- [datasets/data/_schema/columns.schema.json](datasets/data/_schema/columns.schema.json) - bump `x-version` + new `x-changelog` entry
- [backend/tests/test_csv_columns.py](backend/tests/test_csv_columns.py) - bump the version assertion to 2.1
- [frontend/src/contracts/csv-columns.ts](frontend/src/contracts/csv-columns.ts) - add the file-class glob if a registry exists there

**Column block for event_summary.csv**:

```json
"datasets/data/datapoints/electoral/event_summary.csv": {
  "notes": "Per-event aggregate: one row per (event_id, state_code) tuple. scope=national row collapses General-election rows across states (state_code=null); scope=state rows are per-Assembly. Built by `python -m yen_gov derive-event-summary` from per-state election_results.csv + per-event summary.csv. leading_party_id is the canonical party (or alliance) with most seats; alliance attribution flows through the writer per Hans verdict 2026-06-15. turnout_pct is event-scope: SUM(votes_polled) / SUM(electors) * 100. Spec: TODO/20260615-elections-redesign-plan.md row E1.",
  "columns": [
    { "name": "event_id",          "dtype": "string",  "nullable": false, "pk": true },
    { "name": "state_code",        "dtype": "string",  "nullable": true,  "pk": true },
    { "name": "scope",             "dtype": "string",  "nullable": false, "enum": ["national", "state"] },
    { "name": "kind",              "dtype": "string",  "nullable": false, "enum": ["parliament", "assembly", "assembly_bye", "general_bye", "by_election"] },
    { "name": "polled_on",         "dtype": "string",  "nullable": false },
    { "name": "leading_party_id",  "dtype": "string",  "nullable": true,  "fk": "datasets/data/entities/parties.csv.party_id" },
    { "name": "seats_won",         "dtype": "integer", "nullable": false },
    { "name": "seats_contested",   "dtype": "integer", "nullable": false },
    { "name": "turnout_pct",       "dtype": "float",   "nullable": true },
    { "name": "runner_up_party_id","dtype": "string",  "nullable": true,  "fk": "datasets/data/entities/parties.csv.party_id" },
    { "name": "runner_up_seats",   "dtype": "integer", "nullable": true },
    { "name": "source_id",         "dtype": "string",  "nullable": false, "fk": "datasets/data/entities/source.csv.source_id" }
  ]
}
```

**Composite PK** = `(event_id, state_code)` because General-election rows have state_code=null (one row per event_id) while Assembly rows have state_code populated. The NULL-in-PK is intentional and matches the precedent in [datasets/data/entities/electoral_district_membership.csv](datasets/data/entities/electoral_district_membership.csv).

**Acceptance gates**:

- `pytest backend/tests/test_csv_columns.py -k "version"` green with bumped 2.1.
- Frontend `csv-columns.ts` registry resolves the new file-class (or the registry's glob already covers `datasets/data/datapoints/electoral/*.csv`).
- `bun run check` green in `frontend/`.

**Oracle**: `python -c "import json; s=json.loads(open('datasets/data/_schema/columns.json').read()); print(len(s['file_classes']['datasets/data/datapoints/electoral/event_summary.csv']['columns']))"` returns `12`.

**Dependencies**: none.

**Reviewers**: Hans (FK shape), Fowler (schema discipline), Gregor (contract surface).

### Row E2 - Backend event_summary_writer + CLI + Tier-B receipt

**Scope**: New writer module + new Typer CLI command + pytest + actual emit of the CSV. Idempotent: re-running on unchanged input yields byte-identical output. Per Hans verdict, the writer is the place where alliance-as-leading-party attribution happens (consults `datasets/data/entities/party_alliances.csv` at write time; if the top seat-holder is part of a recognised alliance, the writer emits the alliance label).

**Files touched**:

- [backend/yen_gov/canonical/adapters/electoral/event_summary_writer.py](backend/yen_gov/canonical/adapters/electoral/event_summary_writer.py) - NEW
- [backend/yen_gov/cli.py](backend/yen_gov/cli.py) - register `derive-event-summary` Typer command
- [backend/tests/test_event_summary_writer.py](backend/tests/test_event_summary_writer.py) - NEW; fixtures with synthetic election_results rows; verify output shape + turnout aggregation + leading-party derivation + idempotence
- [datasets/data/datapoints/electoral/event_summary.csv](datasets/data/datapoints/electoral/event_summary.csv) - NEW emit; ~309 data rows
- [datasets/data/entities/source.csv](datasets/data/entities/source.csv) - +1 row if writer attributes the aggregate to a new derived source row (deterministic via `derive_source_id("yen-gov", "Per-event election summary aggregate", vintage)`); if a suitable upstream summary row already exists, reuse and skip the append
- [docs/architecture/data/canonical-store.md](docs/architecture/data/canonical-store.md) - new "event_summary" sub-section naming the writer + the rebuild trigger
- [TODO/_TEMPLATE-ingest-handover.md](TODO/_TEMPLATE-ingest-handover.md) - add a "rebuild event_summary" bullet to the post-ingest checklist

**Writer logic**:

```text
for each per-state file under datasets/data/datapoints/electoral/<slug>_election_results.csv:
    rows = read_csv(path)
    for each (event_id, state_code) group:
        seats_by_party = group.group_by(party_id).sum(seats)
        leading = max(seats_by_party, key=seats)
        runner_up = sorted(seats_by_party)[-2]
        turnout_pct = sum(votes_polled) / sum(electors) * 100  (from per-event summary.csv)
        IF leading.party_id is in party_alliances.csv for (event_id, state):
            leading_party_id = alliance label
        ELSE:
            leading_party_id = leading.party_id
        emit row
for each Parliament event_id (6 collapsed-national rows):
    aggregate ALL state-shards into one national row
    same logic; state_code = null; scope = "national"
sort by (polled_on desc, event_id, state_code)
write to datasets/data/datapoints/electoral/event_summary.csv
```

**Acceptance gates**:

- `pytest backend/tests/test_event_summary_writer.py -q` passes.
- `python -m yen_gov derive-event-summary --root .` exits 0 and emits 309 +- 5 rows.
- `python -m yen_gov validate --root .` delta=0 vs baseline.
- `head -2 datasets/data/datapoints/electoral/event_summary.csv` shows header + first row (e.g. `general-2024,,national,parliament,2024-06-04,parties.IN.BJP,240,543,66.0,parties.IN.INC,99,src-...`).
- Re-run the writer: `git diff datasets/data/datapoints/electoral/event_summary.csv` is empty (idempotence).

**Oracle**: Two consecutive runs yield identical `sha256sum`. Spot-check: `general-2024` row has `leading_party_id=parties.IN.BJP`, `seats_won=240`, `seats_contested=543`.

**Dependencies**: E1 (schema must exist for Tier-A to accept the file).

**Reviewers**: Fowler (writer shape, idempotence), Hans (alliance attribution semantics), Max (sourcing).

### Row E3 - Frontend event-summary-loader + 2 view-models

**Scope**: The single seam that loads the new CSV + two derived view-models for the two routes. No UI yet; this PR is reader-only.

**Files touched**:

- [frontend/src/lib/elections/event-summary-loader.ts](frontend/src/lib/elections/event-summary-loader.ts) - NEW; exports `loadEventSummary(): Promise<EventSummaryRow[]>` + `EventSummaryRow` type. Singleton-promise cache. Reads via DuckDB-WASM `read_csv(columns=...)` per CLAUDE.md anti-pattern "no JSON projections of canonical data".
- [frontend/src/lib/view-models/general-elections-model.ts](frontend/src/lib/view-models/general-elections-model.ts) - NEW; derives the 6 General-election rows (scope=national); computes turnout delta vs previous General event; sorts by polled_on desc. Exports `GeneralElectionRowViewModel[]`.
- [frontend/src/lib/view-models/assembly-elections-model.ts](frontend/src/lib/view-models/assembly-elections-model.ts) - NEW; derives one card per state (latest scope=state row); appends 5 "no-legislature" card stubs for `andaman-and-nicobar-islands`, `chandigarh`, `dadra-and-nagar-haveli-and-daman-and-diu`, `ladakh`, `lakshadweep` (cite `frontend/src/routes/StateOverview.svelte` NO_ASSEMBLY_UT_SLUGS); sorts by ECI code default. Exports `AssemblyCardViewModel[]`.
- [frontend/src/lib/elections/event-summary-loader.test.ts](frontend/src/lib/elections/event-summary-loader.test.ts) - NEW unit; mocks `read_csv`; verifies shape + cache memoisation.
- [frontend/src/lib/view-models/general-elections-model.test.ts](frontend/src/lib/view-models/general-elections-model.test.ts) - NEW unit; synthetic 8-row fixture across 3 events; verifies turnout-delta + ordering.
- [frontend/src/lib/view-models/assembly-elections-model.test.ts](frontend/src/lib/view-models/assembly-elections-model.test.ts) - NEW unit; synthetic 12-row fixture across 6 states; verifies latest-only collapse + no-legislature card injection.
- [frontend/src/contracts/elections-summary-coverage.test.ts](frontend/src/contracts/elections-summary-coverage.test.ts) - NEW Tier-A contract; loads the SHIPPED event_summary.csv via vite-served `/data/data/datapoints/electoral/event_summary.csv`; asserts PK uniqueness + FK to election_events.json + `0 <= turnout_pct <= 100` + `seats_won + runner_up_seats <= seats_contested`.

**View-model shapes** (illustrative; finalise in PR):

```ts
export interface GeneralElectionRowViewModel {
  event_id: string;            // "general-2024"
  year: number;                // 2024
  polled_on: string;           // "2024-06-04"
  leading_party_id: string;    // "parties.IN.BJP" or alliance label
  leading_short: string;       // "BJP" (joined from parties.csv)
  leading_color: string;       // hex from getPartyColor()
  seats_won: number;           // 240
  seats_contested: number;     // 543
  vote_share_pct: number | null;
  turnout_pct: number | null;
  turnout_delta_pp: number | null;  // null for the earliest event
  runner_up: { id: string, short: string, color: string, seats: number } | null;
  runner_up_2: { id: string, short: string, color: string, seats: number } | null;
  detail_href: string;  // "/t/elections/general-2024"
}

export interface AssemblyCardViewModel {
  state_code: string;     // "S22"
  state_slug: string;     // "tamil-nadu"
  state_name: string;     // "Tamil Nadu"
  has_legislature: boolean;
  latest_event?: {  // present when has_legislature
    event_id: string;
    year: number;
    polled_on: string;
    leading_party_id: string;
    leading_short: string;
    leading_color: string;
    seats_won: number;
    seats_contested: number;
    turnout_pct: number | null;
    detail_href: string;  // "/tamil-nadu/elections/assembly-2026"
  };
  state_hub_href: string;  // "/tamil-nadu"
  total_events_on_record: number;
}
```

**Acceptance gates**:

- `bun run test -- event-summary-loader general-elections-model assembly-elections-model elections-summary-coverage` all pass.
- `bun run check` green.
- No new mocks beyond the loader's `read_csv`.
- No new corpus-scaling tests (CLAUDE.md anti-pattern: bounded canaries only).

**Oracle**: `elections-summary-coverage.test.ts` reads the live CSV and the live election_events.json; test passes iff PK uniqueness + FK closure + turnout sanity hold.

**Dependencies**: E2 (CSV exists on disk; served by vite middleware).

**Reviewers**: Fowler (test tier + caching), Jony (view-model shape matches rendering needs).

### Row E4 - RIP-AND-REPLACE: 2 routes + nav tabs + delete firehose + home rail

**Scope** (per Section 0.2 doctrine - ONE PR, no parallel-surface period):

1. NEW `frontend/src/routes/GeneralElections.svelte` - mounts `general-elections-model`; renders the 6-row General-elections table per Jony Section 1 spec + Section 0.1 naming.
2. NEW `frontend/src/routes/AssemblyElections.svelte` - mounts `assembly-elections-model`; renders the 41-card Assembly grid per Jony Section 1 spec + Section 0.1 naming.
3. NEW `frontend/src/lib/elections/ElectionsRouteTabs.svelte` - shared nav tab strip per Section 0.1 Jony D2 verdict (ARIA tablist, Tailwind pill family reuse, mobile-friendly).
4. DELETE `frontend/src/routes/ElectionsFirehose.svelte` - the entire 700-line firehose (the IntersectionObserver + promise pool are inlined here; no separate pool file exists).
5. EDIT `frontend/src/main.ts` - swap `ElectionsFirehose` -> `GeneralElections` at `/t/elections`; register `/t/elections/assemblies` -> `AssemblyElections` BEFORE the existing `/t/elections/:event` route.
6. EDIT `frontend/src/lib/elections/crumbs.ts` (or wherever the firehose crumb factory lives) - rename `electionsFirehoseCrumbs` -> `generalElectionsCrumbs`; add `assemblyElectionsCrumbs`.
7. EDIT `frontend/src/lib/elections/HomeElectionsRail.svelte` - door card subtitle: "General + Assembly elections" or similar honest copy reflecting the split.
8. EDIT view-model glue for home-elections-rail if a subtitle is data-driven.
9. NEW `frontend/e2e/elections-routes.spec.ts` - Playwright covering both routes + tab nav + click-into-detail flows.

**Files touched** (consolidated list):

- NEW [frontend/src/routes/GeneralElections.svelte](frontend/src/routes/GeneralElections.svelte)
- NEW [frontend/src/routes/AssemblyElections.svelte](frontend/src/routes/AssemblyElections.svelte)
- NEW [frontend/src/lib/elections/ElectionsRouteTabs.svelte](frontend/src/lib/elections/ElectionsRouteTabs.svelte)
- DELETE [frontend/src/routes/ElectionsFirehose.svelte](frontend/src/routes/ElectionsFirehose.svelte)
- EDIT [frontend/src/main.ts](frontend/src/main.ts)
- EDIT [frontend/src/lib/elections/crumbs.ts](frontend/src/lib/elections/crumbs.ts) (rename + add)
- EDIT [frontend/src/lib/elections/HomeElectionsRail.svelte](frontend/src/lib/elections/HomeElectionsRail.svelte)
- EDIT [frontend/src/lib/view-models/home-elections-rail.ts](frontend/src/lib/view-models/home-elections-rail.ts) (if subtitle is data-driven)
- NEW [frontend/e2e/elections-routes.spec.ts](frontend/e2e/elections-routes.spec.ts)
- DELETE any orphan import of `ElectionsFirehose` across `frontend/src/**`

**GeneralElections route render contract**:

| Column         | Cell content                                                                                |
| -------------- | ------------------------------------------------------------------------------------------- |
| Year           | `<a href={detail_href}>{year}</a>` - tabular-nums, bold, blue underline                     |
| Leading party  | Tailwind pill: party-color background + party_short text + seat-count "240 of 543"          |
| Vote-share bar | Inline `div w-32 h-2 bg-slate-200 rounded`; child `div h-full bg-{color} rounded w-{pct}%`  |
| Turnout        | "66.0%" tabular-nums                                                                        |
| Delta          | `+2.1pp` green-up arrow / `-1.3pp` red-down arrow / `-` for earliest                        |
| Runners-up     | Two pills (party_short + seat-count)                                                        |

Mobile (`< 640px`): collapse to 4 columns: Year | Leading party pill (with seats inline) | Turnout (with delta inline below) | (no runners-up; no vote-share bar).

**AssemblyElections route render contract** (one card per state):

```text
+--------------------------------+
| Tamil Nadu     11 elections    |
| Latest: 2026                   |
| [TVK 108 of 234]  87.1%        |
|                                |
| 2026 -> drill-down            |   <- year IS the link
+--------------------------------+
```

No-legislature UT card:

```text
+--------------------------------+
| Chandigarh                     |
| No state legislature           |   <- slate-500 italic copy
| View district data ->          |
+--------------------------------+
```

Sort controls above the grid: `Place (default) | Most recent | Turnout`. Place uses ECI code order.

Mobile (`< 640px`): single-column stack. All card content remains visible (no hiding).

**ElectionsRouteTabs render contract**:

```text
[ General elections (active)  ]  [ Assembly elections (link) ]
                                         H1 below
```

- ARIA: `<nav role="tablist" aria-label="Elections views">` + `<a role="tab" aria-current="page">` on the active pill
- Tailwind pill family: same active/inactive classes as the firehose body-filter (lift the exact classes for symmetry)
- Mobile: full-width row, pills `flex-1`, no scroll
- Single prop: `current: "general" | "assembly"`
- Mounted at top of BOTH `GeneralElections.svelte` and `AssemblyElections.svelte` ABOVE the H1

**Acceptance gates**:

- All E3 tests still green (no regression on view-models).
- New Playwright `elections-routes.spec.ts` covers both routes + tab nav navigation.
- `bun run check` green.
- `bun run build` green; bundle should SHRINK (firehose was ~700 LOC; new code is leaner because aggregation moved to the writer).
- §13 browser smoke (mandatory per CLAUDE.md):
  - Navigate `/t/elections` -> H1 "General elections", tabs visible, "General elections" pill is active, 6 rows render with year-links + turnout delta on 5 of 6.
  - Click the "Assembly elections" tab -> URL becomes `/t/elections/assemblies`, H1 "Assembly elections", "Assembly elections" pill is now active.
  - 41 Assembly cards (36 + 5 no-leg), Chandigarh shows "No state legislature", no party pill on no-leg cards.
  - Click a leading-party pill on Tamil Nadu card -> navigates to `/parties/<slug>`.
  - Click the year link on Tamil Nadu card -> navigates to `/tamil-nadu/elections/assembly-2026`.
  - Click "General elections" tab from Assembly route -> back to `/t/elections`.
  - No new `[error]` console events, no 404, no `firehose` text leaks anywhere in the rendered DOM.
- `grep -r "ElectionsFirehose\|electionsFirehoseCrumbs\|Elections firehose\|elections firehose" frontend/src/` returns 0 matches.
- First-paint metric: time-to-`[data-testid="general-elections-table-row-general-2024"]`-visible <= 800ms on localhost (current firehose: 2.4s + 41s hydration; rip-and-replace target: <=800ms).

**Oracle**: Playwright `elections-routes.spec.ts` asserts:

1. Both routes render in <= 2s on localhost.
2. Tab nav clicks change URL + active pill.
3. General route has exactly 6 rows; first row is 2024 with `seats_won=240, seats_contested=543`.
4. Assembly route has exactly 41 cards (36 states + 5 no-leg); 5 cards bear `data-testid="card-no-legislature"`.
5. Tamil Nadu Assembly card's year-link navigates to `/tamil-nadu/elections/assembly-2026`.
6. `grep` for "firehose" in the rendered DOM returns 0.

**Dependencies**: E3 (view-models exist + tests green).

**Reviewers**: Jony (visual + tab affordance + mobile), Fowler (deletion discipline + bundle size + first-paint metric), Hans (no-leg honest copy + nav copy), §13 browser smoke.

### Row E5 - CM backfill: 5 states' 2026 incumbents (independent; ships any time)

**Scope**: Curator data PR. Backfills `office_holdings.csv` for the 5 states that polled in 2026-Apr/May. Per the audit (2026-06-15):

| State             | Office     | Current row (OPEN, blank holder)    | Required action                                                                                                               |
| ----------------- | ---------- | ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Assam (S03)       | IN-S03-CM  | term_start=2026-05-13, holder=""    | Fill holder_id (the elected CM's slug)                                                                                        |
| Kerala (S11)      | IN-S11-CM  | term_start=2026-05-13, holder=""    | Fill holder_id                                                                                                                |
| Tamil Nadu (S22)  | IN-S22-CM  | term_start=2026-05-13, holder=""    | Fill holder_id                                                                                                                |
| West Bengal (S25) | IN-S25-CM  | term_start=2026-05-13, holder=""    | Fill holder_id                                                                                                                |
| Puducherry (U07)  | IN-U07-CM  | (no 2026 row; 2021 row still open)  | CLOSE the 2021 row (term_end=2026-05-12) + APPEND a 2026-05-13 OPEN row with holder_id (per indiavotes: Rangaswamy re-elected)|

**Files touched**:

- EDIT [datasets/data/datapoints/office_holdings.csv](datasets/data/datapoints/office_holdings.csv) - 5 surgical edits
- EDIT [datasets/data/entities/holder.csv](datasets/data/entities/holder.csv) - APPEND new holder rows for any CM not yet in the register
- EDIT [datasets/data/entities/source.csv](datasets/data/entities/source.csv) - APPEND citation rows via `derive_source_id(producer, title, vintage)`; ONE row per state suffices
- EDIT [datasets/taxonomy/office_holdings.json](datasets/taxonomy/office_holdings.json) - parallel edits in the seed if the CSV is regenerated rather than hand-edited
- EDIT [docs/concepts/office-holders.md](docs/concepts/office-holders.md) - append a 2026 worked-example block (Rangaswamy Puducherry close + new term as the example of how a re-elected CM splits across rows)

**Sourcing** (per Section 3 Q2 sign-off): wiki or open-web source acceptable. The existing `office_citations` pattern (per-state wiki article) is the easy default. For states where the wiki article lags, an open-web news source (PIB / NDTV / Hindustan Times / The Hindu) is acceptable provided the `source.csv` row carries `owner + title + vintage + url`. The plan does NOT name specific CMs (curator resolves via the live source at PR-author time).

**Acceptance gates**:

- `python -m yen_gov validate --root .` delta=0.
- `pytest backend/tests/test_office_holdings_*.py -q` green.
- Per-(office_id, term_start) PK uniqueness preserved.
- For Puducherry: exactly 2 rows under IN-U07-CM in the 2021-2026 window (one closed at 2026-05-12, one open from 2026-05-13).
- For S03/S11/S22/S25: the 2026-05-13 row has non-empty holder_id.

**Oracle**: Audit script reports: 0 CM rows with `term_start>=2026 AND holder_id=""`. Currently reports 4.

**Dependencies**: none. Ships independently of E1-E4.

**Reviewers**: Hans (source attribution), Max (sourcing discipline).

## Section 3 - Sign-off receipts (closed 2026-06-15)

User verdicts captured 2026-06-15 - executing agent inherits these without re-asking:

| Q | Decision | Source |
|---|---|---|
| Q1 (strategy) | TWO routes (General + Assembly); nav glue via shared tab strip per Section 0.1 Jony D2 verdict | "ok for two routes but they should be navigable and discoverable - jony work on that, dont make it ugly make it intuitive work with citizen" |
| Q2 (CM sourcing) | Wiki OR open-web source acceptable | "2 - cm sourcing. wiki or internet should be good" |
| Q3 (out-of-scope) | Per-event drill-downs untouched | "3 - agreed" |

Additional binding directives (Section 0.1 + Section 0.2):

- "Elections firehose" name RETIRED; "General elections" + "Assembly elections" + "Elections" parent breadcrumb per Section 0.1 ("lets not call it election firehose").
- "Lok Sabha" / "Vidhan Sabha" Hindi-script labels RETIRED; English-only ("lok sabha or vidha sabha wording no hind just english works state assembly or parliment or something similar").
- **Rip-and-replace doctrine**: ship new routes + delete old firehose in ONE PR (E4). No strangler-fig. Git is rollback ("RIP AND REPLACE - NO STRANGLER FIG. GIT IS BACKUP. NO PRISONERS MOVE FORWARD BOLDLY REIMAGINE.").

## Section 4 - Plan-wide acceptance gates

Verify after E1-E5 all DONE:

- `bun run test` green in `frontend/`.
- `bun run e2e -- elections-routes home` green.
- `bun run check` green (svelte-check + tsc).
- `pytest -q` green in `backend/`.
- `python -m yen_gov validate --root .` delta=0 vs baseline.
- New `/t/elections` General-elections page first-paint <= 800ms on localhost (measured).
- Old firehose deleted from repo (`grep -r "ElectionsFirehose\|Elections firehose" .` returns 0 outside of `TODO/` + `docs/archive/`).
- Doc cross-links updated; `docs/architecture/data/canonical-store.md` mentions event_summary.csv.

## Section 5 - Closure ritual

When all rows are DONE:

1. Run `docs/how-to/distill-a-plan.md` ritual.
2. Lift durable findings into the right `docs/` home:
   - `event_summary.csv` aggregate doctrine -> `docs/architecture/data/canonical-store.md`
   - No-legislature-UT-card honest copy -> `docs/concepts/place-first-ia.md`
   - Inline progress-bar vote-share pattern (plain Tailwind, not a new component) -> `docs/concepts/schema-is-the-design-system.md`
   - ElectionsRouteTabs as a reusable nav pattern (only one consumer for now; revisit after second sibling-routes case lands) -> note in `docs/concepts/schema-is-the-design-system.md` extension log if a second consumer appears
3. Archive this plan-doc to `docs/archive/plans/20260615-elections-redesign-plan.md` with the distillation receipt at the top.
4. Update `docs/reference/decision-index.md` if any inline ADR-equivalents were minted (E1's schema bump is a documentation-routing concern, not an ADR).

## Section 6 - Persona convergence transcript (binding ruling)

### Jony verdict (UX) - persona-1 pass

Two routes serve two distinct citizen questions. The General-election time-series question is OWID-aligned; the place-first state question is atlas-aligned. Conflating them defeats both. The right-arrow "Open" affordance is replaced by year-as-link (text that navigates is the existing primitive). Vote-share is an inline Tailwind progress-bar (closed-set faithful). Mobile collapses to 4 columns on General and a single-column card stack on Assembly. UTs without legislature get an honest single-line card with no party pill - the absence of "Latest election" IS the signal.

### Hans amendment (governance) - persona-1 pass

Ratifies Jony's layout split. Adds: (1) leading-party-of-the-winning-alliance attribution for coalition eras flows through the WRITER (not the renderer). (2) Turnout delta is a two-point diff vs prior same-body event (OWID standard) with green-up / red-down glyph. (3) The 5 UTs without legislature get honest copy per ADR-0022 constitutional-honesty. (4) The CM backfill cites the existing wiki / open-web pattern - no new citation mechanism is invented; the Puducherry row-split is the only structural action. (5) The CM citation may be wiki OR open-web per user verdict 2026-06-15.

### Fowler amendment (engineering) - persona-1 pass

Ratifies Jony + Hans. Adds: (1) ONE aggregate CSV at `datasets/data/datapoints/electoral/event_summary.csv` serves both routes; do NOT split the writer. (2) Reader-before-writer: schema lock (E1) BEFORE writer ships (E2). (3) ONE Tier-A contract test (`elections-summary-coverage.test.ts`) enforces PK uniqueness + FK closure + turnout sanity. (4) Per-event drill-down detail pages stay on `loadElectionResults()` - they were not the slowness; the firehose's 313 individual scans were.

### Naming + nav convergence (Citizen + Hans + Max + Jony) - persona-2 pass

The persona-2 pass closed the naming + nav questions per Section 0.1 verdict block. Citizen: "general elections" + "assembly elections" match search intent; tab strip makes the sibling route always one tap away. Hans: "general election" + "assembly election" are constitutionally honest and Wikipedia-aligned. Max: English-literal phrasing survives any future localisation. Jony: tab-pill primitive reuses the existing Tailwind pill family; no new chrome; file names mirror H1 nouns; URL asymmetry preserves link equity. The verdict is binding per Section 0.1 and is NOT re-litigated by the executing agent.

### User direction overrides (2026-06-15)

- "Elections firehose" name retired (Section 0.1).
- Lok Sabha / Vidhan Sabha Hindi labels retired (Section 0.1; English-only per existing PR-0 policy).
- Rip-and-replace doctrine (Section 0.2): one PR for the route swap + firehose deletion. Git is the rollback path. No strangler-fig. Persona-1's three-PR "ship-then-delete" sequencing is OVERRIDDEN.

### Rejected alternatives (anti-re-litigation)

- **Top-10 + paginate.** Rejected by Jony: pagination is opaque to a citizen comparing across eras.
- **Multiple decade-split routes.** Rejected by Hans: methodology breaks cross decade boundaries.
- **Client-side cache + concurrent prefetch all 315.** Rejected by Fowler: trades latency on first visit for a 31 MB CSV burst that fails on 4G.
- **Hybrid: backend writer + keep IntersectionObserver as fallback.** Rejected by Fowler: parallel-surface code paths are technical debt by construction.
- **Mount DualAxisBarLine composite mode for the inline vote-share bar.** Rejected by Jony: over-engineering for a single-cell decorative indicator.
- **Cite state gazette swearing-in for CM backfill.** Deferred: wiki + open-web is sufficient per user verdict 2026-06-15.
- **Keep "firehose" name.** Rejected: user-vetoed 2026-06-15.
- **Use "Lok Sabha" / "Vidhan Sabha" labels.** Rejected: user-vetoed 2026-06-15 + already covered by existing English-only policy.
- **Ship E4 in three separate PRs (route1, route2, deletion).** Rejected: user mandated rip-and-replace 2026-06-15.
- **Add a secondary breadcrumb cross-link instead of tab strip.** Rejected by Jony Section 0.1 D2: cross-links are easy to miss; tab strip is the strongest discoverability primitive at the cost of 1 small component.

---

## Execution contract (autonomous - follow blindly, do not re-plan)

When this plan is in context and the instruction is "implement it", execute as the ORCHESTRATOR with NO further questions except at an ESCALATE trigger. There is no processing step after this block - the rules below are the whole instruction set.

1. **Orchestrator + subagent-PR topology.** The main agent owns the Status Reckoner and never lets its own context overflow. Each PR-row is dispatched to a stateless `runSubagent` brief that is self-contained: the row scope, the files, the acceptance gates, and the one oracle. The subagent does the row; the orchestrator merges and moves on.
2. **One row = one PR = one branch.** Park master on a `scratch-master-parking` branch so no worktree owns `main` (clean gh-merge). Author per `docs/how-to/ship-a-pr.md`: 2-commit-then-squash, the 5-gate Definition-of-Done, browser-verify for any frontend/admin runtime change.
3. **Ship loop, non-stop.** Keep PRs in flight; never idle. As soon as one row's gates are green, merge (`gh pr merge --squash --delete-branch`), pull main, start the next row. Pre-existing unrelated test failures are not gating - document the baseline, do not block.
4. **Tests ship with the row.** Write/update only the tests the row needs. Full suite green at merge. No new mocks unless asked.
5. **Persona debate converges to ONE ruling.** When a row hits a contested design call, run the authority personas (CLAUDE.md section 0a) in debate, not parallel review; bake the single written verdict into the row and proceed. For this plan, naming + nav are already converged (Section 0.1); do not re-litigate.
6. **Manage context via offload.** Push breadth-y reads, audits, and exploration into subagents so the orchestrator's window stays lean. The orchestrator holds only the Reckoner, the current row, and the merge state.
7. **Post-merge hygiene every time.** Delete the remote branch, prune `: gone` local branches, remove `.tmp_*`, distill durable lessons.
8. **Stop only at a real boundary.** Stop and ask ONLY when: an ESCALATE trigger fires (Section 0 ESCALATE list), an explicit user-named source/instruction would be scope-narrowed (STOP-AND-SURFACE per CLAUDE.md section 10), or an audit chain exceeds depth 3 (escalate with Path A/B/C options). Otherwise do not pause; the user is not watching.
9. **Closure.** Done only when every in-scope row is DONE or COLLAPSED-with-cited-rationale. No-op rows carry a receipt. Archive the plan-doc with a per-row distillation map per `docs/how-to/distill-a-plan.md`.

## See also

- [CLAUDE.md](../CLAUDE.md) - engineering contract (section 0a authority, section 6 levels, section 10 anti-patterns).
- [docs/concepts/schema-is-the-design-system.md](../docs/concepts/schema-is-the-design-system.md) - closed renderer set + one card per measure.
- [docs/architecture/frontend/url-grammar.md](../docs/architecture/frontend/url-grammar.md) - ADR-0028 + ADR-0037 + ADR-0052 + English-only chrome PR-0.
- [docs/concepts/office-holders.md](../docs/concepts/office-holders.md) - term-shape spine for CM backfill.
- [docs/concepts/citizen-first.md](../docs/concepts/citizen-first.md) - Citizen-bookend doctrine.
- [docs/concepts/place-first-ia.md](../docs/concepts/place-first-ia.md) - ADR-0022 constitutional-honesty rule.
- [docs/architecture/testing.md](../docs/architecture/testing.md) - four-tier test matrix.
- [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md) - PR lifecycle referenced by the EXECUTION BLOCK.
- [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md) - closure ritual.

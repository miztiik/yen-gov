# ECI Statistical Report — Multi-State Ingest Plan

**Status**: Planning (2026-05-11). Aligns with [IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR](IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR.md) doctrine.
**Correction Levels**: N1 = L2, N2 = L3, N3 = L4, N4 = N/A (already shipped).

## Scope reset

The admin GUI's ECI Recon panel can now download raw XLSX/PDF for **all 15 pinned states** (2024-2026 cohort). The gap is parsed-emit (`datasets/elections/...`) which works for **May-2026 only** because it cross-fetches a partywise URL from `results.eci.gov.in/Result<event>/...` that only exists for that event.

Non-API states (2022/2023 per ECI's own listing — UP, Karnataka, Telangana, etc.) are on the legacy portal as static PDFs and need a different ingest entirely.

## Storage decision (load-bearing, do NOT change)

**`datasets/elections/<event>/<state>/` stays.** Per IA-reset doctrine, election artifacts keep their own schema family; "elections as one of many indicators" is a **catalogue/UI** statement, not storage. Restructuring to `datasets/indicators/in/elections/` would (a) collide with what the parallel agent shipped in P1+P2 and (b) explicitly contradict the doctrine line *"no forcing election results into long-form indicator rows"*.

The catalogue ([datasets/reference/in/topic-catalogue.json](../datasets/reference/in/topic-catalogue.json)) already represents elections as `{ "kind": "election", ... }` peer to fiscal/welfare. That's where the demotion lives.

## Sequenced plan

### N1 — Expose emit + decouple `--event` from the CLI signature (L2, this session)

Today `eci-statreport-emit` defaults `--event AcGenMay2026`, which is meaningful for 5 states and meaningless for the other 10. Two parts:

1. **Add an `event` registry** at `backend/yen_gov/sources/eci/events.py` with `(state_code, year) → event_id` mappings, mirroring `categories.py`. Initially only the 5 May-2026 entries; future events extend the registry.
2. **CLI**: derive `--event` from `(state, year)` via the registry when not explicitly passed; explicit flag still overrides.
3. **GUI**: add a "🚀 Full ingest" button on each pin row, **enabled only when the event registry has an entry**. Disabled buttons get a tooltip "no event registered for (S01, 2024) — see N2".

This makes the button safe (no crashes from running emit on AP 2024) and surfaces the gap without papering over it.

**Done = GUI shows ⬇ XLSX (raw), ⬇ +PDF (raw), and 🚀 Full ingest (only on May-2026 pins) for each pin.**

### N2 — Source partywise from Section 4, decouple from results portal (L3)

`eci-statreport-emit` cross-fetches a `partywise` HTML page to get numeric `eci_code` for each party short code. ECI's Statistical Report **already includes this**: Section 4 ("List of Political Parties Participated") has the same data in XLSX form for every state.

Switch the emit pipeline to:

1. Parse Section 4 instead of the live-results partywise HTML.
2. Drop the `--event`-derived URL builder from this code path entirely.
3. Output path becomes `datasets/elections/<event>/<state>/` where `event` is still required (it's the on-disk grouping) but no longer constrains where data can be sourced from.

Once N2 lands, **all 15 pinned states unlock for full per-AC ingest**, regardless of whether their results portal still serves HTML.

Risk: Section 4 schema across states needs sampling — formats may differ between 2024 (Andhra) and 2026 (TN). One inspection pass before coding the parser.

### N3 — Legacy portal (2022-2023) — DEFER

Twenty states (2022 cohort: Goa, Gujarat, HP, Manipur, Punjab, UP, Uttarakhand; 2023 cohort: Chhattisgarh, Karnataka, MP, Meghalaya, Mizoram, Nagaland, Rajasthan, Telangana, Tripura) have NO entry in the new ECI API (catalogue ends at category_id=27). Their data lives at `https://eci.gov.in/files/file/<id>-...pdf` on the legacy portal.

Approaches if/when prioritized:
- (a) **Manual PDF table extraction** with `pdfplumber` — accurate but slow per state.
- (b) **Find a third-party ETL** (myneta.info, opencityprojects, datameet) and ingest from there with provenance pointing to both upstream and the original ECI PDF.
- (c) **Wait for ECI back-fill** — they are rebuilding the legacy data into the new API gradually.

**Recommendation**: defer until at least 5 of the 15 API-supported states have full ingest shipped. Don't optimize for the harder cohort first.

### N4 — Indicator-first IA — ALREADY DONE

Per [IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR.md](IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR.md) P1+P2 (shipped 2026-05-11):

- `topic-catalogue.json` exists and groups indicators with election as one polymorphic kind.
- StateOverview reads sections from the catalogue.
- AcGenMay2026 no longer leaks into citizen-visible chrome.
- Display string is "Tamil Nadu Assembly · May 2026" via the catalogue's `display` field.

No work needed in this slice. P3-P5 of that plan continue independently.

## Sequencing

```
NOW    →  N1 (expose emit button, decouple --event default)            this session
NEXT   →  N2 (Section 4 → unlock 15 states)                            ~half day, sample first
LATER  →  N3 (legacy portal)                                            week+
PARALLEL → IA-reset P3-P5 (other agent owns; do not touch)
```

## Honest caveats for the user

- N1 alone unlocks **zero new state** for full ingest. It's a wiring fix that prevents crashes and makes the gap visible. The unlock is N2.
- N2 unlocks **15 states for parsed per-AC datasets** — most of the ECI's modern catalogue.
- N3 covers another 17 states but is the hardest fetcher work in the project.
- The public app's renderer paths still point at `datasets/elections/AcGenMay2026/`. Even after N2 lands data for, say, AP 2024, the citizen-facing app needs the routes to know about `<event>=AE-2024-AP` (or whatever event id we register). That's a separate small piece per event.


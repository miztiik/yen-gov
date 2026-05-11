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

### N2 — Source partywise from Section 4, decouple from results portal (L3) — SHIPPED with revised approach

**Recon finding (2026-05-11)**: Section 3 (List of Political Parties Participated) — NOT Section 4 as originally guessed — carries `(party_type, abbreviation, full_name)` triplets but NOT the numeric `eci_code` (e.g. 742 for BJP). The numeric code is published ONLY on the live-results portal partywise page. So Section 3 cannot replace partywise for archived events.

**Approach taken**: branch the emit pipeline on a `has_partywise: bool` flag in the events registry.
- **has_partywise=True** (5 May-2026 pins): unchanged behaviour — partywise cross-fetch + reconciliation + parties.json.
- **has_partywise=False** (10 archived pins, 2024+2025): fetch Section 3 instead of partywise, leave `party_eci_code: null` on candidates (schema-allowed), skip reconciliation, skip `parties.json` (its schema requires numeric eci_code which we don't have).

This unlocks all 15 pinned states for parsed per-AC ingest, with the explicit understanding that the 10 archived ones lose the canonical party roster + the partywise reconciliation cross-check. The admin GUI surfaces this with an asterisk on the button label and an amber-700 (vs amber-500) tint.

**Followup deferred**: a one-time backfill of `eci_code_by_short` from notification.eci.gov.in (party registration notifications) could resolve nulls retroactively without needing partywise. Not in N2 scope.

**Verified**: `eci-statreport-emit S21 2024` ran clean against ECI's live API, produced 32 schema-valid AC results, then was rolled back (the new event needs `datasets/events/in/eci/AcGenJun2024/election.json` metadata before it can land in the repo — separate per-cohort decision).

### N3 — Legacy portal (2022-2023) — STILL DEFERRED

Unchanged from original framing. Twenty states (2022 + 2023 cohorts) have NO entry in the new ECI API; their data lives at `https://eci.gov.in/files/file/<id>-...pdf` on the legacy portal. PDF table extraction is week+ work per state.

**Why still deferred even after N2 shipped**: the ten newly-unlockable archived 2024-2025 states need `datasets/events/in/eci/<event>/election.json` cohort metadata before their parsed data can land in the repo (the integrity test enforces this). That's 5 cohorts of metadata work + per-state route additions in the public app. Doing N3's hard fetcher work BEFORE consuming the easy N2 data is bad ordering.

**Recommended next slice if N3 truly wanted**: pick ONE state from N2's pool (e.g. S07 Haryana 2024 or U05 Delhi 2025), author its `election.json`, ingest it, wire up a public-app route, and learn what the rendering layer actually needs from a partywise-less event. THEN decide whether N3 is worth the cost.

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


# P.1.A C5+C6 retire-list audit — design lock vs on-disk reality

**Last Updated**: 2026-05-24 (Path A CHOSEN)
**Status**: ◧ DESCOPE-AND-PIVOT. Audit of the 16-shard retire-list in [`20260524-p1a-c5-c6-canonical-reader-design.md`](20260524-p1a-c5-c6-canonical-reader-design.md) §4 / §6 against on-disk canonical reality reveals **8 of 16 shards cannot safely retire as planned**. C5 reader + C6 retire is DESCOPED until the data-mismatch is resolved. **Path A (§3 below) CHOSEN 2026-05-24**: retire the 8 SAFE shards now, defer the 8 unsafe into 4 follow-up lift PRs. The re-acquisition schedule for those 4 lift PRs is at [`20260524-p1a-data-reacquisition-plan.md`](20260524-p1a-data-reacquisition-plan.md).
**Doc class**: plan-doc handover per [ADR-0034](../../architecture/decisions/0034-documentation-routing-contract.md).
**Authority routing**: Hans + Max (data fidelity) for what's actually retire-able, Gregor (read-seam contract) for the partial-retire shape, Fowler (strangler-fig discipline) for the canonical-lift-first ordering.
**Cites**: [P.1 energy pivot plan-doc](20260522-phase-2-p1-energy-pivot.md) §4 + §6 (the retire-list that this audit invalidates) + [C5+C6 design doc](20260524-p1a-c5-c6-canonical-reader-design.md) (the planning doc this audit pauses) + [`20260524-p1a-data-reacquisition-plan.md`](20260524-p1a-data-reacquisition-plan.md) (the Path A re-acquisition schedule) + `/memories/lessons.md` 2026-05-22 PR #88 G.1 descope (the procedural precedent for this kind of mid-execution pivot).

---

## §1. Discovery summary

The retire-list design in [§4 / §6 of the C5+C6 planning doc](20260524-p1a-c5-c6-canonical-reader-design.md) split 16 legacy energy shards into "9 hard drops" and "7 reader-replaceable" based on **conceptual mapping** of legacy indicator-id to canonical indicator-id. A pre-implementation audit running each pair through the actual on-disk Parquets revealed that **conceptual mapping does not match data shape**:

- **5 "replaceable" shards are CEA Monthly Executive Summary snapshots** (35 entities, single period 2026-03) but the canonical fact-tables hold NITI ICED time series (6–36 entities, 2015-04..2025-04, depending on fuel). These are different data products from different publishers, not different views of the same data.
- **3 "hard-drop" shards hold data the canonical does not yet carry**:
  - `state_installed_capacity_total_mw.json` covers FY04-14 (305 rows pre-canonical); canonical only goes back to 2015-04
  - `state_installed_capacity_by_source_mw.json` has 1815 rows; canonical has 1137 (legacy holds 678 unique rows)
  - `state_electricity_peak_demand_mw.json` includes 2025-04 (canonical caps at 2024-04)
- **8 shards ARE truly retire-safe** — covered below in §2.

Also surfaced: legacy entity-id format (`S07`, `U05`) ≠ canonical format (`IN-S07`, `IN-U05`). Any reader-switch implementation MUST normalise; this is a smaller fix but undocumented in the planning doc.

## §2. Per-shard audit verdict

Inspector tool: `tools/inspect_c5_full_audit.py` (kept in this PR as a regression artifact; can be re-run any time to validate the audit).

### A. SAFE to retire (8 of 16)

| Shard | Class | Legacy | Canonical equivalent | Verdict |
| --- | --- | --- | --- | --- |
| `installed_mw_by_state.json` | HARD-DROP | 14 rows, 4 states, 2019 | none (Datameet community-curated) | Holy Law #9 fail; safe retire |
| `installed_capacity_total_mw.json` | HARD-DROP | 35 rows, 2026-03 snapshot | sum-on-read of 5 fuel atoms | D33.8 compute-on-read; safe |
| `installed_capacity_thermal_mw.json` | HARD-DROP | 35 rows, 2026-03 | sum-on-read of `coal` + `gas` | D33.8 compute-on-read; safe |
| `installed_capacity_by_source_mw.json` | HARD-DROP | 186 rows, 2026-03 (composer) | UNION-on-read of 5 fuel atoms | Composer; safe IF the 5 fuel-snapshot shards are kept (see §2.B) |
| `state_installed_capacity_geographical_mw.json` | REPLACEABLE | 407 rows, 37 entities, 2015-04..2025-04 | `state-installed-capacity-geographical-mw` (407 / 37 / 2015-04..2025-04) | **BYTE-PARITY-LIKELY**; safe |
| `state_installed_capacity_with_alloc_mw.json` | HARD-DROP | 396 rows, 36 entities, 2015-04..2025-04 | `state-installed-capacity-allocated-mw` (396 / 36 / 2015-04..2025-04) | Same rowcount / entity / period; alias; safe |
| `state_electricity_generation_mu.json` | HARD-DROP | 407 rows, 37 entities, 2015-04..2025-04 | `state-electricity-generation-gwh` (407 / 37 / 2015-04..2025-04) | MU=GWh alias; same data; safe |
| `state_peak_electricity_demand_mw.json` | HARD-DROP | 33 rows, 33 states, 2025-04 (single snapshot) | `state-peak-electricity-demand-mw` (396 / 34 / 2013-04..2024-04) | Canonical is superset minus 2025-04; safe IF Hans accepts losing 2025-04 single-snapshot (LIKELY: 2025-04 is one publication window away from the canonical's 2024-04 tail) |

**8 ready to retire in a future C6 PR.** No new lift required.

### B. NEEDS canonical lift FIRST (5)

| Shard | Legacy data | Canonical gap |
| --- | --- | --- |
| `installed_capacity_coal_mw.json` | CEA Monthly Exec Summary 2026-03; 35 entities | Canonical has NITI ICED 2015-2025 series (18 entities); MISSING 2026-03 35-state snapshot |
| `installed_capacity_gas_mw.json` | CEA 2026-03; 35 entities | Canonical 2015-2025 series (22 entities); MISSING 2026-03 snapshot |
| `installed_capacity_hydro_mw.json` | CEA 2026-03; 35 entities | Canonical 2015-2025 series (26 entities); MISSING 2026-03 snapshot |
| `installed_capacity_nuclear_mw.json` | CEA 2026-03; 35 entities | Canonical 2015-2025 series (6 entities — only states with nuclear plants); MISSING 2026-03 snapshot |
| `installed_capacity_renewable_mw.json` | CEA 2026-03; 35 entities | Canonical 2015-2025 series (36 entities); MISSING 2026-03 snapshot |

**Root cause**: P.1.A C4 lift adapter (PR #102) sourced the per-fuel canonical fact-table from NITI ICED Capacity Metatable API (`src-ba5c6fa6acfe`), which carries 2015-04..2025-04 annual data but does NOT carry the most recent CEA Monthly Executive Summary snapshot. The 2026-03 snapshot at 35-entity granularity is unique to the CEA publication and is not yet in canonical.

**Recommended path**: P.1.A C4.5 "CEA-snapshot lift" PR that EXTENDS `energy_installed_capacity.parquet` with new indicator rows like `state-installed-capacity-mw-coal-snapshot` (entity_id = `IN-Sxx`, period_label = `2026-03`, source_id = `src-092a5dc7af3f`). Then these 5 shards become retire-able. **Estimated scope**: 5 new indicator_ids × 35 entities = 175 new canonical rows + 5 catalogue rows + 5 legacy-shard retires + Tier-B allowlist scrub. ~3-day PR.

### C. NEEDS Hans+Max review (3)

| Shard | Legacy data | Canonical gap |
| --- | --- | --- |
| `state_installed_capacity_total_mw.json` | 712 rows, 35 entities, **FY04-FY24** | Canonical only carries FY15-FY25; **305 FY04-FY14 rows would be LOST** if retired today |
| `state_installed_capacity_by_source_mw.json` | 1815 rows, 36 entities, 2015-04..2025-04 | Canonical has per-fuel children summing to 1137 rows; legacy holds **678 unique rows** (likely entities with rare fuel mixes that ICED filtered out) |
| `state_electricity_peak_demand_mw.json` (separate from §2.A row above) | 305 rows, 34 entities, 2017-04..2025-04 | Canonical 396 / 34 / 2013-04..2024-04 carries earlier data; legacy holds **2025-04 single-snapshot rows unique to it** |

**Recommended path**: Either (a) lift the missing data to canonical first (similar to §2.B), or (b) Hans+Max sign off that the lost data is acceptable (e.g. FY04-14 may be excluded if pre-CEA-online methodology era and the data is suspect anyway). Either way, NOT retire-able today without an explicit data-loss decision.

## §3. Three forward paths

### Path A — Retire the 8 safe shards, defer the 8 unsafe (CHOSEN 2026-05-24)

**Status**: ✅ CHOSEN. Re-acquisition plan for the deferred 8 + the 1 SAFE-retired shard losing FY25 data: [`20260524-p1a-data-reacquisition-plan.md`](20260524-p1a-data-reacquisition-plan.md).

**Scope**: Smaller C6 PR retiring the 8 §2.A shards + scrubbing their 8 allowlist entries + amending `canonical-store.md` §2b (the §2b amend is data-shape, not retire-list-dependent). C5 reader infrastructure ships in the same fused-atomic commit BUT path-router only handles the 8 retired paths + a catch-all for the 8 deferred paths that falls through to legacy.

**Why**: Honest. Ships real value (8 file deletions). Forces the Hans+Max design decision on the deferred 8 via a separate handover. Splits a 16-file commit into two 8-file commits, each independently reviewable.

**Risk**: The reader-switch design is somewhat awkward when only HALF the family is canonical-backed. Worth eating today vs an "all 16" commit that ships data loss. The 1 SAFE-retired shard with a single-window FY25 loss is restored in the very next PR per the re-acquisition plan §3 C4.7 (~1 day, additive lift, no decisions needed).

### Path B — Pause C5+C6 entirely, ship a "lift CEA snapshot" PR first (P.1.A C4.5)

**Scope**: NO C5+C6 work this iteration. A separate C4.5 PR extends canonical to carry the CEA 2026-03 snapshot (5 new indicator rows, 175 new fact-rows). Then C5+C6 ships against the full retire-list.

**Why**: Cleanest sequencing. C5 reader gets to assume all 16 paths route to canonical. §2b amend ships once with the full 5-fact-table set.

**Risk**: Longer wall-clock to a value-delivering retire. C4.5 design also needs a Hans+Max verdict on the snapshot's identity (separate indicator? extended same indicator with new period?).

### Path C — Accept the data change, retire all 16 anyway (rejected)

**Scope**: Ship the original C5+C6 plan; citizen-visible regression on 8 indicators (5 fuel snapshots disappear; FY04-14 total-MW disappears; 2025-04 peak demand disappears).

**Why rejected**: Hans authority over citizen-surface data fidelity per CLAUDE.md §0a. Silent data loss is not acceptable even when the canonical store will eventually subsume it.

## §4. Recommendation

**Path A** ships honest value today with explicit honesty about deferrals. Path B is also acceptable if Hans prefers single-PR completeness over phased delivery. Path C is doctrinally wrong per §0a.

The two paths share **THIS PR's deliverable**: doc-only descope, amend the planning doc + the prior C5+C6 design doc to mark the retire-list INVALIDATED, ship this finding doc as the binding artifact for the next agent / future session to resume from.

**Verdict (2026-05-24)**: Path A CHOSEN. Re-acquisition schedule for the deferred 8 + lost FY25 single window lives at [`20260524-p1a-data-reacquisition-plan.md`](20260524-p1a-data-reacquisition-plan.md). 4 follow-up sub-PRs (C4.7 / C4.5 / C4.6 / C4.8) sequenced behind the Path A retire PR.

## §5. Sub-PR shape (THIS PR — doc-only descope)

| File | Action | Why |
| --- | --- | --- |
| `docs/archive/plans/20260524-p1a-c5-retire-list-audit-findings.md` (new, this doc, ~210 lines) | CREATE | The binding handover |
| `docs/archive/plans/20260522-phase-2-p1-energy-pivot.md` (plan-doc) | EDIT | §4 last unchecked item annotated: "BLOCKED on retire-list reaudit, see 20260524-audit-findings.md"; §6 hard-drops table annotated with audit verdict per row |
| `docs/archive/plans/20260524-p1a-c5-c6-canonical-reader-design.md` (prior planning doc from PR #116) | EDIT | Header status changes to "🛑 DESIGN-PAUSED — retire-list invalidated by 20260524-audit-findings.md; choose Path A or Path B before code starts" |
| `tools/inspect_c5_full_audit.py` (new) | CREATE | Regression artifact — re-runnable to revalidate any future retire-list change |

No code change. No schema change. No data change. Zero test gates impacted.

## §6. Process lessons (for /memories/lessons.md)

1. **Conceptual-map verification ≠ data-shape verification.** The C5+C6 planning doc's "16-shard retire list" was built by mapping `legacy indicator id` → `canonical indicator id` via NAME similarity. Name-similarity is necessary but not sufficient: the underlying data may be a snapshot vs a time series, a publisher's monthly vs another publisher's annual, a 35-state vs an 18-state coverage. ALWAYS run the conceptual map through `read_parquet` + `len(rows)` + `set(entity_id)` + `min/max(period_label)` BEFORE the planning doc gets a design-lock stamp.

2. **Audit-before-stage cost = 30 seconds; audit-after-stage cost = hours.** This audit took 3 inspector scripts (~150 LOC total) and ~5 minutes to run. Would have been ~hours of revert-and-rewrite work to discover post-`git rm` of the 16 shards.

3. **Re-confirms 2026-05-22 PR #88 G.1 descope pattern**: when audit contradicts on-disk reality mid-execution, DESCOPE + handover. Don't push through. Don't switch to Plan-mode (loses write tools). Just persist the finding, write the binding doc, ship a smaller PR.

4. **This is the 2nd time this conversation an audit caught a stale planning doc** (the first was the PR #115 §4 pre-flight checklist where the summary claimed 0 unchecked items but on-disk verified 7/8 already flipped). Lesson: planning docs from prior sessions are debate-output. On-disk is execution-input. When they disagree, on-disk wins AND the doc gets corrected.

## §7. Cross-refs

- [C5+C6 design doc (PR #116)](20260524-p1a-c5-c6-canonical-reader-design.md) — the planning doc this audit invalidates the retire-list portion of
- [P.1 energy pivot plan-doc](20260522-phase-2-p1-energy-pivot.md) §4 + §6 — the source of the retire-list
- [PR #102 C4 lift adapter](https://github.com/miztiik/yen-gov/pull/102) — the lift that sourced NITI ICED 2015-2025 series (and did NOT lift CEA 2026-03 snapshot)
- /memories/lessons.md 2026-05-22 PR #88 G.1 descope (procedural precedent)
- /memories/lessons.md 2026-05-22 G.1.a entity-lift audit-vs-reality (the same kind of mismatch)
- `tools/inspect_c5_full_audit.py` (this PR) — runnable regression audit

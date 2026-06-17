# CEA + ICED faceted-ingestion modernization plan

**Last Updated**: 2026-06-17
**Level**: 5 (core ingestion pipeline + data-shape). Authority: Hans + Max (data shape) / Gregor (contract) / Fowler (craft) per CLAUDE.md section 0a.
**Status**: AWAITING USER RATIFICATION. No adapter code is written until the recommended rulings in section 0.4 are ratified or amended.
**Branch (plan-doc only)**: `feat/cea-iced-faceted-ingest`. Scope is **CEA + ICED only** - RBI is owned by another agent and is OUT.

---

## 0. Operating contract

### 0.1 Why this plan exists

PR #1097 (merged) established the faceted canonical datapoint contract: fuel-faceted measures live in
`datasets/data/datapoints/geo_by_fuel/<measure>.csv` (`entity_id, time, fuel_type, value, source_id`;
composite PK; `fuel_type` closed enum `[coal, gas, hydro, nuclear, renewable, all]`). The pending
ICED/CEA energy data the user wants ingested currently has **no path** into this contract: the
`cea_installed_capacity` + `iced_power` source adapters are stale across FOUR migrations and emit the
old, now-illegal per-fuel shape.

This plan is the corrected follow-on to the closed PR #1099 (a premature fence). It was opened after
a STOP-AND-SURFACE: the documented "reconcile the adapters" is not a column-add, it is a Level-5
modernization rewrite with embedded data-shape decisions.

### 0.2 The verified drift (read against code, not the draft)

The `sources/{cea_installed_capacity, iced_power}` adapters are stale across:

| # | Drift | Adapters emit | Current contract |
| --- | --- | --- | --- |
| 1 | Entity key | ECI codes (`S22`, `U05`, `IN`) via `iced_common.ENTITY_MAP` | LGD slugs (`andhra-pradesh`, `IN`). No clean ECI->slug crosswalk (`state_codes.csv` keys on lgd_state_id / iso_3166_2 / slug / aliases) |
| 2 | Indicator id | `installed-capacity-mw`, `electricity-generation-snapshot-gwh`, `thermal-capacity-retired-mw` | `installed-capacity-{geographical,snapshot}-mw`, `electricity-generation-gwh` |
| 3 | Fuel collapse | raw upstream fuels (`small-hydro`, `oil-gas`, `bio-power`, `solar`, `wind`, `waste-to-energy`) | 5-bucket `{coal, gas, hydro, nuclear, renewable}` (Hans D33.8). The `SUB_FUEL_TO_CANONICAL` map was DELETED in `8ea74f243`; recoverable from git |
| 4 | Shape | N per-fuel files under `geo/` | ONE faceted `geo_by_fuel/<measure>.csv` |

**Historical pipeline (now obsolete):** `sources/*` parsed raw -> meadow JSON
(`datasets/energy/_meadow/<source>/<vintage>/*.json`); the deleted `canonical/adapters/energy/`
package lifted meadow -> Parquet. The G5 / energy-livestock migration then converted Parquet -> CSV;
PR #1097 faceted the CSV. The meadow -> Parquet chain is dead (the store is CSV). So the modern shape
is a **single pass**: parse -> 5-bucket collapse -> ECI->slug -> faceted CSV.

### 0.3 Hard constraints

- **CAPABILITY-ONLY.** No raw inputs are on disk (`.runtime/raw/cea/` absent; network fetch deleted in
  B4-pt2). Every row delivers emit *capability* proven by `tmp_path` fixture tests + a CLI entry point;
  **no committed `geo_by_fuel/` data** for cea/iced is produced (it emits when an operator stages raw
  inputs and runs the CLI). The plan states this on every row so no agent waits for real data.
- **RBI is OUT** (another agent owns `rbi_xlsx` + net-transfers). Do not touch them.
- **Schema-version is moving.** `columns.json` is at 2.7 (from #1097). A concurrent SDG-overlay PR also
  bumps to 2.7 (will rebase to 2.8) and adds `frameworks.csv` / `goals.csv` / `goal_indicators.csv`.
  This plan MUST stay version-agnostic, add no new file-class that needs a bump unless escalated, and
  not touch the SDG file-classes.

### 0.4 Recommended rulings (RATIFY or AMEND before any code)

Persona subagents were unavailable this run (model-config error); these are the orchestrator's
synthesis applying each authority's doctrine. The user is the final authority (section 0a) and
ratifies here.

| Ruling | Lens | RECOMMENDED resolution |
| --- | --- | --- |
| **R-A Revive vs rewrite** | Gregor + Fowler | **HYBRID.** Keep the `sources/*` parsers (the CEA-XLSX column decode + ICED AES-JSON decode is genuine, hard-won value). REWRITE only the emit + entity + id + collapse layer into a thin single-pass that writes the faceted CSV directly. Do NOT revive the deleted meadow->Parquet `canonical/adapters/energy/` package (obsolete). Delete the stale per-fuel emit functions. |
| **R-B Entity seam** | Gregor | ECI->LGD-slug translation lives in ONE shared helper all energy adapters call (not per-adapter). **ESCALATE risk:** if no clean ECI->LGD-slug crosswalk can be derived from `state_codes.csv` (aliases) or an existing seed, minting a new authoritative crosswalk seed is a Hans+Max data-shape call - stop and surface. |
| **R-C CEA family + fuels** | Hans + Max | CEA = "Executive Summary on Power Sector" monthly snapshot, state-grain -> `installed-capacity-snapshot-mw`. `total` -> `fuel_type=all`; `thermal` (coal+lignite+gas+diesel composite, not a D33.8 bucket, derivable, unconsumed) -> **DROP** from the facet axis (if "total thermal" earns citizen value it is a separate single-value indicator, deferred). |
| **R-D ICED capacity family** | Hans + Max | ICED capacity-metatable, state-grain -> `installed-capacity-geographical-mw`, with `SUB_FUEL_TO_CANONICAL` 5-bucket collapse + `total`/sum -> `all`. |
| **R-E ICED generation** | Hans + Max + Fowler | **DEFER to its own PR.** Generation faceting is incomplete even on the frontend (still per-fuel; no `geo_by_fuel/electricity-generation-gwh.csv`). Faceting it is a #1097-style effort (FE migration + consolidate); do not entangle the pilot. |
| **R-F Retired-capacity** | Max | **DEFER / drop.** National-only, 2-fuel, ORPHAN (no FE consumer). Revisit only if a citizen surface needs it. |
| **R-G Peak-demand** | Fowler | Single-value, already canonical-shaped under `geo/peak-electricity-demand-mw.csv`. Only the entity-key (ECI->slug) fix applies; minor. |
| **R-H Guardrail fence** | Gregor | Re-add the closed-#1099 fuel-facet fence LAST, once the emit path exists, so it guards a satisfiable contract. Scope it to installed-capacity (cea/iced); leave the net-transfers part to the RBI agent. |

### 0.5 ESCALATE triggers (stop, surface, wait)

- R-B: no clean ECI->LGD-slug crosswalk exists -> minting an authoritative seed is Hans+Max.
- Any need for a NEW file-class or a `columns.json` bump (collides with the moving SDG version).
- R-E generation faceting (a Level-4 FE migration) if pulled in.
- Any disagreement with a ratified ruling in 0.4 surfaced mid-execution.

---

## 1. Status Reckoner

| Row | Title | Status | PR | Effort |
| --- | --- | --- | --- | --- |
| 0 | ECI -> LGD-slug shared entity crosswalk seam | [ ] PENDING | - | S-M (ESCALATE if no crosswalk) |
| 1 | Restore `SUB_FUEL_TO_CANONICAL` as a shared helper (from git) | [ ] PENDING | - | S |
| 2 | PILOT: CEA installed-capacity -> faceted `geo_by_fuel/installed-capacity-snapshot-mw` + CLI + fixture tests | [ ] PENDING | - | M |
| 3 | ICED capacity-metatable -> faceted `geo_by_fuel/installed-capacity-geographical-mw` + CLI + fixture tests | [ ] PENDING | - | M |
| 4 | Peak-demand entity-key fix (single-value) | [ ] PENDING | - | S |
| 5 | Re-add fuel-facet guardrail fence (folded #1099, now satisfiable) | [ ] PENDING | - | S |
| D1 | DEFERRED: ICED generation faceting (own FE-migration PR) | [ ] DEFERRED | - | - |
| D2 | DEFERRED: retired-capacity orphan disposition | [ ] DEFERRED | - | - |

---

## 2. Per-row specs

### Row 0 - ECI -> LGD-slug shared entity crosswalk seam
- **Scope:** establish ONE helper that maps the adapters' entity output (ICED state-name / ECI code)
  to the canonical LGD slug used by `entities/geo.csv`. Investigate first whether `state_codes.csv`
  aliases or an existing seed already carries the mapping; if not -> ESCALATE (Hans+Max seed mint).
- **Files:** new shared module under `backend/yen_gov/sources/iced_common/` (or `canonical/`); a unit test.
- **Oracle:** for every ICED state-name in `ENTITY_MAP`, the helper resolves to a slug that exists in
  `datasets/data/entities/geo.csv.entity_id` (FK-closed), or the row ESCALATES with the unmapped set.
- **Capability-only:** yes (no data emitted).

### Row 1 - Restore SUB_FUEL_TO_CANONICAL
- **Scope:** recover the deleted 5-bucket collapse map (git `8ea74f243^:backend/yen_gov/canonical/adapters/energy/_shared.py`) into a small shared, tested helper; no other behaviour.
- **Files:** new `backend/yen_gov/sources/iced_common/fuel_collapse.py` (or similar) + unit test.
- **Oracle:** unit test pins every upstream label -> canonical bucket (oil-gas->gas; small-hydro/solar/wind/bio-power/biomass/waste-to-energy->renewable; coal/hydro/nuclear/gas/renewable direct) and that the codomain is exactly the 5 buckets.

### Row 2 - PILOT: CEA installed-capacity faceted emit
- **Scope:** rewrite CEA's emit (keep its parser) to produce ONE faceted file
  `datasets/data/datapoints/geo_by_fuel/installed-capacity-snapshot-mw.csv` with rows
  `{entity_id(slug), time, fuel_type, value, source_id}`: map the 5 fuel columns 1:1, `total`->`all`,
  drop `thermal`; translate entity via Row 0; add a `@app.command` local-file ingest entry.
- **Files:** `sources/cea_installed_capacity/ingest.py` (emit rewrite), `backend/yen_gov/cli.py` (new command), `backend/tests/test_cea_installed_capacity_csv_repoint.py` (rewrite to the faceted shape).
- **Oracle:** a `tmp_path` fixture run emits exactly one file whose header is the `geo_by_fuel/*.csv`
  5-column contract, `fuel_type` values are a subset of the enum incl `all`, and `validate_csv`
  passes (FK + enum + composite-PK).
- **Capability-only:** yes.

### Row 3 - ICED capacity-metatable faceted emit
- **Scope:** same pattern for ICED capacity -> `geo_by_fuel/installed-capacity-geographical-mw.csv`,
  applying the Row 1 collapse to the raw sub-fuels + Row 0 entity translation + sum->`all`; CLI entry.
- **Files:** `sources/iced_power/ingest.py` (capacity emit only), `cli.py`, `test_iced_power_csv_repoint.py` (capacity assertions).
- **Oracle:** fixture run emits one faceted file; raw `small-hydro`/`oil-gas` collapse to `renewable`/`gas`; `validate_csv` passes.

### Row 4 - Peak-demand entity-key fix
- **Scope:** ICED peak-demand stays a single-value `geo/peak-electricity-demand-mw.csv`; only re-point
  its entity output through the Row 0 slug translation.
- **Oracle:** fixture run emits slug-keyed rows that FK-close to `geo.csv`.

### Row 5 - Re-add the fuel-facet guardrail fence
- **Scope:** recover the closed-#1099 `tier_b_no_refragmented_fuel_facet_csv` (from `origin/fix/energy-adapter-facet-reconcile`), scope it to the installed-capacity families (leave net-transfers to the RBI agent), register in `validate.run()`.
- **Oracle:** the 7 fence unit tests + 0 violations on the live corpus (now there is also a satisfiable faceted-emit path).

### Deferred (explicit, with receipts)
- **D1 ICED generation faceting:** needs a #1097-style FE migration (`indicator-allowlist` per-fuel ->
  faceted) + `geo_by_fuel/electricity-generation-gwh.csv`. Own PR; Hans+Max+Fowler.
- **D2 retired-capacity:** orphan, no FE consumer; revisit on demand.

---

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

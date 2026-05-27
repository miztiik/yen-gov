# 2026-05-22 — Phase 2 P.1 NFHS-5: planning handover (archived; superseded by Energy pivot)

> **ARCHIVED 2026-05-22** — This planning doc was drafted on the assumption that **Phase 2 P.1 = NFHS-5**. The user clarified on 2026-05-22 that **Phase 2 P.1 = Energy** (Option E in the agent's "which family next" question; the agent had defaulted to NFHS-5 based on a wrong reading of `§0e.7 P.*` ordering — the Max-recommended ordering in `§0e.2 Q7` was NFHS-5 → PLFS → UDISE+ → ..., but the user's choice supersedes per CLAUDE.md §0a). The NFHS-5 plan content below is preserved for the eventual NFHS-5 P.\* row when it lands later in Phase 2; nothing in this doc has been merged or shipped. The active Phase 2 P.1 plan now lives at [`docs/archive/plans/20260522-phase-2-p1-energy-pivot.md`](plans/20260522-phase-2-p1-energy-pivot.md).

---

# 2026-05-22 — Phase 2 P.1 NFHS-5: planning handover

> **Status**: ⏳ NOT DONE — PLANNING with locked design (Hans + Max + Jony round 2026-05-22). No code shipped from this doc. Per CLAUDE.md §6 a P.\* family pivot is Level 4–5 work, so it earns a planning artifact + breakdown proposal **before** any backend or schema commit. This doc is that artifact. **Design is now LOCKED** (see §"Locked design 2026-05-22" below); next commit is `feat/p1-nfhs-5-backend` (single PR per Max — NOT split A/B/C/D).

## Authority routing (per CLAUDE.md §0a "The One Rule")

| Decision class | Authority for P.1 |
| --- | --- |
| Indicator selection (which NFHS-5 metrics make P.1 vs which defer to P.1.b/c/…) | **Max** (lead) + Hans (governance framing) |
| `datasets/health/` family directory + table naming | **Hans + Max** (data shape); refer to canonical-store.md §2a |
| Source identity for `sources.parquet` (one row vs many; issuing-authority cardinality) | **Max** (citation ledger discipline, OWID precedent) |
| Pydantic / DuckDB writer integration | **Gregor** (contracts), **Fowler** (refactor safety) |
| URL slugs + page templates + map/chart UX | **Jony + Citizen** |

User pre-clears any of the above when direct user direction is on record.

## What NFHS-5 is (background, no decisions)

**National Family Health Survey, round 5** (2019–21). Conducted by the **International Institute for Population Sciences (IIPS), Mumbai**, on commission from the **Ministry of Health and Family Welfare (MoHFW), Government of India**, with **ICF (DHS Program)** as the technical partner. Largest household survey in India after the Census; sample frame ~636,699 households across all 707 districts.

**What the citizen knows it for**: infant mortality (IMR), under-5 mortality (U5MR), total fertility rate (TFR), maternal anaemia, child stunting / wasting / underweight, institutional delivery share, full immunisation coverage, household electricity / sanitation / cooking-fuel access. Hans flagged these as the high-impact citizen-readable indicators in [TODO/PLAN.md `human_development`](PLAN.md) and TODO/SOCIO-ECONOMIC-EXPANSION.md.

**Publication forms**:

| Form | Granularity | Format | URL pattern | Stability |
| --- | --- | --- | --- | --- |
| All-India + State factsheets | National + state | PDF (citizen-friendly tables) | `rchiips.org/nfhs/NFHS-5_FCTS/.../<STATE>.pdf` | Stable (published 2021–22) |
| District factsheets | District | PDF, one per district | `rchiips.org/nfhs/NFHS-5_FCTS/<state>/<state>_District.pdf` (multi-district per file) | Stable |
| State / All-India / District Reports | Full report | PDF + XLSX | `rchiips.org/nfhs/NFHS5_Report.shtml` | Stable |
| API tables (Compendium) | Indicator × state | HTML tables on rchiips.org | Various | Stable, parseable |
| Micro-data | Household / individual | Stata, CSV | DHS Program "data download" (DUA required) | Stable, gated |

**Source identity** (Max's citation-ledger call, ladder candidates):

- **Issuing authority**: IIPS (executes survey, owns methodology); MoHFW commissions and co-publishes.
- **OWID precedent**: NFHS is normally cited as `IIPS, NFHS-5 (2019-21)` with MoHFW as commissioning agency in the footer.
- **Recommendation (subject to Max review)**: One row per RELEASE in `sources.parquet`. v2.0 triple = `(producer="International Institute for Population Sciences", title="National Family Health Survey-5 (NFHS-5)", vintage="2019-21")`. License: `unknown-public` until Hans confirms (NFHS releases are typically free for public reuse; no explicit CC license on the factsheets — needs verification). `is_issuing_authority: true`, `confidence_tier: gold`, `verification_method: live-fetch` (or `archived-snapshot` if we mirror to `.runtime/` before parse).

## Target shape on disk (per canonical-store.md §2b + §0e.4)

```text
datasets/health/
  health_nfhs.parquet              # fact: one row per (indicator_id, entity_id, period, sex_breakdown, area_type) observation
  dim_nfhs_rounds.parquet?         # optional dim: NFHS round metadata (NFHS-1..5 vintage years, sample sizes) — defer to P.1.c
datasets/taxonomy/
  indicators.parquet               # gains health rows for IMR, U5MR, TFR, stunting, etc. — keyed by indicator_id
  sources.parquet                  # gains 1 row for NFHS-5 (per Max recommendation above)
```

**Family name**: `health` (per §0e.4 — split out of `human_development`).
**Fact table name**: `health_nfhs.parquet` (canonical-store.md §2a fact-table rule: `<family>_<role>.parquet`; role = `nfhs` because it identifies the data source / methodology cohort, NOT the indicator).
**Sibling fact tables** (future P.1.b/c/d, in scope of `health` family but NOT in scope of P.1): `health_hmis.parquet`, `health_srs.parquet`, `health_crs.parquet`, `health_phe.parquet`.

**Schema for `health_nfhs.parquet`** (Max + Hans + Gregor draft — subject to design pass before coding):

| Column | Type | Required | Description |
| --- | --- | --- | --- |
| `indicator_id` | string | ✓ | FK → `taxonomy/indicators.parquet`; kebab-case per §0e.3 (e.g. `infant-mortality-rate-nfhs`, `total-fertility-rate-nfhs`, `child-stunting-nfhs`). |
| `entity_id` | string | ✓ | FK → `taxonomy/entities.parquet`; `IN` (all-India), `IN-S22` (Tamil Nadu state), `IN-D<lgd_code>` (district) per §0e.10.2-A grammar. |
| `period_label` | string | ✓ | Publisher's verbatim vintage label (e.g. `"2019-21"`, `"2015-16"` for NFHS-4 backfill if needed). Per §0e.7 P.* "adapter owns its source's vocabulary". |
| `period_year` | int32 | ✓ | OWID integer-year convention; round mid-year (NFHS-5 = 2020). |
| `value_numeric` | double | — | Numeric observation value (null when value_text is used). |
| `value_text` | string | — | Text observation (e.g. categorical breakdown labels). Mutually exclusive with value_numeric per dimension contract. |
| `unit` | string | ✓ | `"deaths_per_1000_live_births"`, `"per_woman"`, `"percent"`, etc. Locked enum on `taxonomy/units.parquet` if it exists; otherwise free-string with Hans review. |
| `sex_breakdown` | string | ✓ | `total`, `male`, `female`, `urban_total`, `rural_total`, etc. NFHS publishes rural/urban + sex breakdowns natively. |
| `area_type` | string | ✓ | `total`, `urban`, `rural`. NFHS factsheet column. |
| `source_id` | string | ✓ | FK → `taxonomy/sources.parquet` (one row per NFHS release per Max recommendation). |
| `methodology_note` | string | — | Brief methodology-break flag (e.g. "Sample boost for state-level estimates in NFHS-5"); citizen reads this in the small-print line under the chart. |

**Hive partitioning**: probably none for P.1 (single round, ~700 districts × ~50 indicators = ~35k rows, ≤2 MB compressed). Defer partition decision until P.1.b when HMIS adds a monthly cadence. Per canonical-store.md §10 the trigger is "≥15 MB". §2b §"observations.parquet # if family ≤ 15 MB; else partition".

## Locked design 2026-05-22 (Hans + Max + Jony round)

User direction (verbatim, 2026-05-22): _"I'm expecting the sources to constantly fluctuate. So we should be planning to process the file, store it, not worry too much about polishing or fine tuning the tooling itself. Once we have the data what we need, we move on to the next source. Conscious pick and choose what we need. Be comprehensive about coverage. Plan it for energy, health, finance with facets underneath."_

The six open questions Q1–Q6 from the draft below were routed to Hans + Max + Jony per CLAUDE.md §0a. Their verdicts are now LOCKED; the option lists below are kept for archive only.

| # | Question | LOCKED verdict | Authority |
| - | --- | --- | --- |
| Q1 | Source format | **HTML compendium tables on `rchiips.org` first; factsheet PDFs as per-indicator fallback** (NOT factsheets-first). Reject DHS-Program micro-data — DUA paperwork is the tooling-friction the user principle vetoes. | Max |
| Q2 | Indicator scope | **ALL ~110 NFHS-5 health indicators in ONE P.1 PR.** Drop the ~20 household-amenity indicators (those belong in the `amenities` family per §0e.4). No tiered P.1.A/B/C/D split — sub-topics (mortality / fertility / nutrition / women's health / immunisation) live as columns on `taxonomy/indicators.parquet`, not as PR boundaries. | Max (overrides draft (c) tiered) |
| Q3 | Sex/area encoding | **Long format with `sex_breakdown` + `area_type` as required dimension columns.** OWID precedent (CLAUDE.md §0a "The One Rule"). | Max + Gregor |
| Q4 | District matching | **Hard-match + taxonomy patch in the SAME P.1 commit.** Pre-flight script captures every NFHS district name that doesn't resolve, the patch lands the missing LGD-keyed rows in `taxonomy/entities.json`, re-run is byte-stable. Reject soft-match — anonymous data violates Holy Law #9 and grows forever. | Hans + Max |
| Q5 | `_OPERATIONAL_STRIP_PATHS` | **KEEP until last P.\* family ships.** Early retirement breaks legacy folded-indicator byte-stability while the 110 remaining shards under `datasets/indicators/in/` are still live-read by the frontend during the P.2–P.10 transition. | Fowler + Gregor + Hans |
| Q6 | Frontend timing | **Split: P.1.A backend + P.1.B frontend.** P.1.B = ONE new `<ParquetIndicatorArtifact>` component rendering IMR-NFHS-5 as a choropleth card inside the EXISTING `/t/health` topic page (which already carries 6 SRS-sourced indicators); no new route, no new chrome. Ship within the same week as P.1.A — don't let backend sit dark. | Jony |

**Source-identity lock** (Max + Hans):

- `sources.parquet` row triple: `producer="International Institute for Population Sciences"`, `title="National Family Health Survey-5 (NFHS-5)"`, `vintage="2019-21"`.
- `source_id` derived via `backend.yen_gov.canonical.citation.derive_source_id` (`src-<12-char hash>`).
- `license="unknown-public"` with `notes` carrying the NDSAP-2012 convention statement Hans drafted: _"MoHFW-commissioned, IIPS-executed; no explicit license stamp on publication PDFs; treated as public-use under NDSAP 2012 convention; reuse with citation per Data For India / Plain Facts precedent."_ Do NOT promote to `OGL-IN-1.0` without an explicit stamp from MoHFW/IIPS.
- `is_issuing_authority=true`, `confidence_tier="gold"`, `verification_method="live-fetch"` (or `archived-snapshot` if we mirror to `.runtime/` before parse).
- `url_main` = the rchiips.org NFHS-5 landing page (the single most stable URL pointing at the round).
- MoHFW does NOT appear in `producer`. NFHS-4 is its own future `sources.parquet` row (not "NFHS series").

**Methodology-break lock** (Hans):

- For P.1 (single round), trust `period_label="2019-21"` + `source_id` to carry round identity. No `dim_nfhs_rounds.parquet` yet.
- `dim_nfhs_rounds.parquet` lifts when NFHS-4 backfill lands (additive, not breaking — defer at zero cost).
- `methodology_note` column is RESERVED for true per-row exceptions (e.g. "Manipur Phase 2 conducted during lockdown — sample displacement; interpret with caution"). NOT for routine round-level metadata.

**J&K / Ladakh seam** (Hans, P.1.A pre-flight gate):

- NFHS-5 fieldwork (2019–21) straddled the October 2019 reorganisation. IIPS published a separate Ladakh factsheet (2 districts: Leh, Kargil).
- `entities.parquet` MUST carry `IN-U07-Ladakh` distinct from post-reorg `IN-S01-J&K` (20 districts, not 22) BEFORE P.1.A's hard-match runs.
- Pre-flight: a 10-line script under `tools/` produces the `NFHS-district-list vs entities.parquet` diff. Missing rows land in `taxonomy/entities.json` in the SAME P.1.A commit.

**Telangana (2014)** is clean — NFHS-5 publishes AP and Telangana as separate state factsheets; no risk.

## Revised sub-PR breakdown

Locked at TWO PRs (NOT four as the draft proposed):

| # | Branch | Scope | Acceptance |
| - | --- | --- | --- |
| **P.1.A** | `feat/p1-nfhs-5-backend` | NEW `datasets/health/` family + ALL ~110 NFHS-5 health indicators (state + district granularity) + NEW `health_nfhs.parquet` writer + NEW `health-nfhs.schema.json` v1.0 + `sources.parquet` row + adapter `backend/yen_gov/sources/nfhs_5/` (HTML-first, PDF fallback) + J&K/Ladakh + missing-district taxonomy patches + ~110 `taxonomy/indicators.parquet` rows + Tier-A fixture tests + Tier-B validator green | `validate: OK`; pytest green; `health_nfhs.parquet` readable via DuckDB CLI; row count matches NFHS-5 compendium |
| **P.1.B** | `feat/p1-nfhs-5-frontend-imr-card` | NEW `<ParquetIndicatorArtifact>` component reading `health_nfhs.parquet` via DuckDB-WASM + IMR choropleth card inserted into existing `/t/health` page + manifest.json update | §13 browser smoke on `/t/health`; vitest + Playwright green |

P.1.A is the critical-path commit. P.1.B is a HARD follow-on, within the same week — invisible data is debt.

## Rejected alternatives (do NOT re-propose)

1. **Land all 131 NFHS indicators in one PR** — multi-day arc with no bisect points. The G.1.c lesson (Hans+Fowler+Max 3-persona review) showed that even a "consolidation" PR benefits from being scoped to one decision; 131 indicators is 131 decisions.
2. **Park NFHS in `datasets/indicators/in/human_development/` as folded JSON shards** — directly contradicts §0e.7 P.\* and CLAUDE.md §10 anti-pattern enforcement (Tier-B forbids new shards under `datasets/indicators/in/`).
3. **Skip the `taxonomy/indicators.parquet` row + read indicator labels straight from `health_nfhs.parquet`** — bricks the M:N topic-tag join (T.3 / §0e.4) and the indicator catalogue page. Indicator identity lives in taxonomy, observations live in the family.
4. **Use micro-data as the day-one source** — DUA + license complexity blocks ship for ~weeks. Factsheet PDFs are publicly available and citation-aligned. Micro-data path stays open via P.1.x if a use case emerges.
5. **Soft-match districts with `IN-DXXX-unmapped-<slug>` placeholders** — violates Holy Law #9 (no anonymous data) and creates a category of rows that the citizen surface has to either hide or render as "Unknown district".

## What this PR doc does NOT decide

- TCPD license (S.1 blocker — see audit doc §A.4).
- Boundaries-as-fifth-P.\*-family (deferred; see audit doc §B.5).
- Operator-state file shape post-Phase-2 (audit doc §A.1).
- Whether `taxonomy/units.parquet` exists yet (Max — quick check; if not, P.1 adds it).
- Whether `taxonomy/indicators.parquet` is the existing v4.4 shape or needs T.3-style bump (audit doc §A.3 frozen-`indicator.schema.json` policy applies; NEW rows on the existing shape only).

## Verification gates (locked from G.1.a/b/c pattern)

Every P.1.x sub-PR ships with:

- [ ] Tier-A fixture-based pytest tests for the writer (`tmp_path`, no real corpus).
- [ ] Tier-B validator green (`python -m yen_gov validate --root .` → `0 issues`).
- [ ] Frontend vitest green (`bun run test --run` in `frontend/`).
- [ ] §13 browser smoke on at least 3 routes when the change is UI-visible.
- [ ] Lockfiles in sync (CLAUDE.md §9 — `bun install` if `package.json` changed).
- [ ] No `[DEBUG]` markers.
- [ ] No `datetime.now()` baked into row content (CLAUDE.md §10).
- [ ] `source_id` FK populated on every observation row (Holy Law #9).

## Provenance

- Created: 2026-05-22 by default agent immediately after G.1.c merge (commit `36e64c87`).
- Trigger: user direction "document deferrals in main plan and start the next phase".
- Authority for shipping P.1: per §0a above — Max leads indicator selection, Hans + Max lock data shape, Gregor / Fowler hold contracts + refactor safety, Jony + Citizen own UX.
- Reading order before starting work: this doc → [audit doc Deferrals section](20260521-phase-2-preflight-audit-gregor.md) → [§0e.7 P.\* row in main plan](20260517-canonical-long-format-pivot.md) → [canonical-store.md §2a-§2b](../docs/architecture/data/canonical-store.md).

## See also

- [docs/archive/plans/20260517-canonical-long-format-pivot.md](20260517-canonical-long-format-pivot.md) §0e.4 (topic taxonomy) + §0e.7 P.\* row (sequencing).
- [docs/archive/plans/20260521-phase-2-preflight-audit-gregor.md](20260521-phase-2-preflight-audit-gregor.md) §"Deferrals & open decisions" (open questions that may affect P.1 design).
- [docs/architecture/data/canonical-store.md](../docs/architecture/data/canonical-store.md) §2a (naming rule), §2b (target tree), §5 (sources contract).
- [docs/architecture/decisions/0030-canonical-store-duckdb-wasm.md](../docs/architecture/decisions/0030-canonical-store-duckdb-wasm.md).
- [docs/architecture/decisions/0032-sources-citation-ledger.md](../docs/architecture/decisions/0032-sources-citation-ledger.md).
- G.1.a/b/c arc as the strangler-fig pattern reference: commits `ee441193` (PR #89), `cc9ad5b7` (PR #90), `36e64c87` (PR #91).

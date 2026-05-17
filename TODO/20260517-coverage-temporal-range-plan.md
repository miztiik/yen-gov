# 20260517 — `coverage.temporal` resolution + structured range on completeness index

**Status:** Phase #1 ✅ shipped; Phase #1.5 ✅ shipped (ADR-0027, cadence field, 4 artifacts retagged); Phase #2 ✅ shipped (completeness schema v2.0, last_polled_at rename, structured temporal fields, determinism test, CLAUDE.md §10 bullet); Phase #3 ✅ shipped (TS `deriveTemporalRange` + `buildTemporalCaption` + cross-language fixture parity + live citizen caption + stale comment removed + e2e + browser smoke); Phase #4a ✅ shipped 2026-05-17.
**Revision:** v3 — Phase #1 spike surfaced a contract gap (decennial/ad-hoc cadences misread as "gaps" by gap_count math). Per parallel Fowler/Gregor/Max debate, Option C added: new optional `indicator.cadence` field (ADR-0027), schema bump v4.0 → v4.1, `derive_temporal_range()` consults cadence and omits gap_count/observed_count for `decennial`/`ad_hoc`. Three artifacts flagged for adapter-quality audit (see Deferred follow-ups).
**Author:** assistant (read-only revalidation pass on `main` @ 07e33b3).
**Context docs:** [CLAUDE.md](../CLAUDE.md) §6, §10, §11, §15; [ADR-0026](../docs/architecture/decisions/0026-lift-collection-inventory-out-of-indicator-artifact.md); [ADR-0027](../docs/architecture/decisions/0027-cadence-as-separate-field-from-time-grain.md); [`indicators-completeness.schema.json`](../datasets/schemas/indicators-completeness.schema.json); [`indicator.schema.json`](../datasets/schemas/indicator.schema.json) v4.1; [`coverage.py`](../backend/yen_gov/coverage.py); [`IndicatorChoropleth.svelte`](../frontend/src/lib/IndicatorChoropleth.svelte).

## Why this exists

After the v3.0 → v4.0 lift (ADR-0026), three live questions remain about temporal-range information:

1. The `coverage.temporal` string is still `required` in every indicator artifact, still free-text. The new `/data-completeness` index gives `observed_count` + `last_collected_at` but **no min..max date range** — so it does not actually replace the operator's "what range did we capture?" glance.
2. The backend still carries a `_parse_temporal()` band-aid (`backend/yen_gov/coverage.py#L308`) that brittle-parses publisher prose, plus a schema-drift bug at line 430 (`row.get("period")` where rows use `time`).
3. The citizen sees no temporal range on the indicator card at all today (only `coverage.spatial` falls through in `IndicatorChoropleth.svelte#L650`).

## Survey of the actual data (110 artifacts)

| Count | Shape | Example |
|---:|---|---|
| 83 | `YYYY-MM..YYYY-MM` | `2015-04..2025-04` |
| 10 | `YYYY..YYYY` | `1961..2011` |
| 9  | `YYYY-MM` (snapshot) | `2026-03` |
| 5  | **prose** | `2014–2023 (annual; 2020 absent — see notes)` |
| 2  | `YYYY-MM-DD` (snapshot) | `2026-05-14` |
| 1  | `YYYY` (snapshot) | `2019` |

The 5 prose entries are all environment AQ series (NO₂, SO₂, PM₁₀, PM₂.₅, FGD share). The prose carries real caveats (gap year, snapshot date).

Crucial: **every artifact already has `rows[].time` (machine token) and `rows[].period_label` (publisher caption).** Range = `min` / `max` over `rows[].time`. We do not need to parse `coverage.temporal` to know the range — we have the rows.

## Decision (recommendation for debate)

**Option (c):** Keep `coverage.temporal` as publisher-owned free-text. Add a structured min/max range to `indicators-completeness.json`, derived from `rows[]`.

Rejected:
- **(a) Do nothing:** leaves the schema-drift bug + parsing band-aid alive, no machine answer to "what range".
- **(b) Restructure `coverage.temporal` into `{min, max, frequency}` inside the artifact:** forces a re-emit of 110 artifacts to surface an operator-only concern, AND bakes a *derived* value into a *publisher-owned* field (category error).

(c) keeps the two audiences (publisher / operator) on separate surfaces that never disagree.

## Concrete shape — completeness index addition (revised post-debate)

Per entry in [`indicators-completeness.json`](../datasets/reference/in/indicators-completeness.json), add seven fields:

```json
{
  "id": "environment/state_pm25_annual_mean_ug_m3",
  "observed_count": 56,
  "min_time": "2018",
  "max_time": "2023",
  "min_period_label": "2018",
  "max_period_label": "2023",
  "observed_periods_within_range": 5,
  "gap_count_within_range": 1,
  "time_grain": "year",
  "last_polled_at": "2026-05-14T23:24:24Z"
}
```

Derivation rules:

- `min_time` / `max_time` = lexicographic min/max of `distinct(rows[].time)`. Same string vocabulary the publisher uses; no normalisation (CLAUDE.md §10).
- `min_period_label` / `max_period_label` = `period_label` of any row holding that `time`, falling back to the `time` token if no label.
- `observed_periods_within_range` = count of distinct `rows[].time` (i.e. how many unique time tokens are actually in the file).
- `gap_count_within_range` = (count of expected periods between min and max at `time_grain` cadence) − `observed_periods_within_range`. **This is what makes the AQ-2020 hole visible without parsing prose.** Example PM2.5: years 2018..2023 = 6 expected; rows present at 2018,2019,2021,2022,2023 = 5 observed; gap_count = 1.
  - Computed only when `time_grain` is one of `year | fiscal_year | quarter | month`. For `date` grain, omit (gaps undefined).
  - For single-period snapshots (`min == max`), gap_count = 0.
- `time_grain` = mirrored from `indicator.time_grain` (a derived projection of the artifact, not a shadow truth — Max's pre-concession against Gregor's anticipated duplication-smell critique).
- `last_polled_at` = `max(sources[].fetched_at)`. **Renamed from `last_collected_at`** (which today's index uses) to make the operator/freshness distinction explicit and stop the field being mistaken for data-vintage. The true "when did data change at source" fix needs upstream `Last-Modified` plumbing and is deferred (see Open question #4).
- All seven absent when `rows == []`. Never fabricate.

**Mixed-vocabulary guard (unanimous debate verdict):** if an artifact's `rows[].time` tokens span more than one detected vocabulary shape (e.g. some `FY 2024-25`, some `2024-04`), the emitter MUST raise `ValueError(f"indicator {id}: heterogeneous rows[].time vocabulary: {vocab_set}")` and surface it through the per-indicator inconsistency channel `coverage.py` already uses. Silent omit was rejected because it overloads the null signal (Gregor) and hides an adapter bug (Fowler) and would break methodology comparability (Max).

Rejected shape variants:
- **Comma-separated list of all observed periods** (raised by user): `observed_count` + `gap_count_within_range` answer count + gap questions; a full list bloats the index ~100× and re-invents `rows[].time`.
- **Single combined `range` string**: loses the machine/citizen split.
- **Derived `coverage.observed_range` block on the artifact** (Gregor's steelman): re-introduces the lifecycle conflation ADR-0026 just lifted out.
- **`entity_coverage_ratio`** (Max's wish-list): defer — ADR-0026 lifted `expected_geographies` to the operator-state overlay so the denominator is no longer artifact-local. Flagged for a follow-up arc, not in scope here.
- **Citizen caption reads `last_polled_at`** (plan v1 implied this): debate consensus is citizen sees data-vintage = `max(rows[].time)` only; `last_polled_at` is operator-only on `/data-completeness`.

## Action items (revised order post-debate)

Fowler's sequencing argument won: extract the pure rule first so #1 and #2 are one-line consumers of an already-tested function. Action numbering changed from v1.

### #1 — Extract `derive_temporal_range()` pure function (Level 2, structural, no behaviour change)
- New function `backend/yen_gov/inventory/derive.py::derive_temporal_range(rows: list[dict]) -> TemporalRange | None` returning the seven derived fields (or `None` for empty rows).
- Fail-loud on mixed vocabulary.
- **Spike step before commit:** run the new function against all 110 artifacts and assert none fail. If any do, that's an adapter bug to fix BEFORE the schema bump lands (discovery, not deploy surprise — Fowler).
- Switch `coverage.py::_scan_indicators` to use the new function. Delete `_parse_temporal()` in the same commit. Fix the `row.get("period")` schema-drift bug at line 430 in the same commit (or it dies with `_scan_indicators` if we delete that too — decide during implementation based on whether the markdown report is still wanted).
- Tests (pytest): one fixture per vocabulary shape (year, fiscal_year, quarter, month, date snapshot), one empty-rows case, one mixed-vocab fails-loud case, one PM2.5-shaped gap case.

### #2 — Bump completeness index schema + emitter + docs atomically (Level 2) — ✅ SHIPPED 2026-05-17

What landed:
- [`indicators-completeness.schema.json`](../datasets/schemas/indicators-completeness.schema.json) bumped **v1.0 → v2.0** (not v1.1 — the `last_collected_at` → `last_polled_at` rename is a breaking change per CLAUDE.md §11; v1.1 in the original plan text was internally inconsistent with the rename being declared breaking in the same bullet).
- Added 8 optional structured fields populated by `derive_temporal_range()`: `min_time`, `max_time`, `min_period_label`, `max_period_label`, `observed_periods_within_range`, `gap_count_within_range`, `time_grain`, `cadence`.
- Extended [`tools/emit_indicators_completeness_index.py`](../tools/emit_indicators_completeness_index.py) to import `yen_gov.inventory.derive_temporal_range` and merge its output into each row; per-row temporal block silently omitted when `rows[]` is empty.
- Regenerated [`datasets/reference/in/indicators-completeness.json`](../datasets/reference/in/indicators-completeness.json) (110 rows, v2.0).
- Renamed in lockstep:
  - [`frontend/src/routes/DataCompleteness.svelte`](../frontend/src/routes/DataCompleteness.svelte) (TS interface + table cell).
  - [`admin/src/lib/api.ts`](../admin/src/lib/api.ts) (TS interface, added optional temporal fields).
  - [`admin/src/routes/Indicators.svelte`](../admin/src/routes/Indicators.svelte) (sort key + column header "Last polled" + cell binding).
  - [`backend/tests/test_admin_indicators.py`](../backend/tests/test_admin_indicators.py) (expected_keys set).
- Determinism guard: [`backend/tests/test_emit_completeness_determinism.py`](../backend/tests/test_emit_completeness_determinism.py) — two-run byte-identity + on-disk-matches-fresh-emit. Both pass.
- CLAUDE.md §10 anti-pattern bullet added: "Do not parse `coverage.temporal` — use the structured fields on the completeness index instead."
- [`docs/architecture/backend/coverage.md`](../docs/architecture/backend/coverage.md) banner added pointing operators at the structured index and flagging the Phase #4a retirement.

Validation:
- Tier-B corpus validator: 0 errors on the changed files (the 1 pre-existing `datasets/ephemeral/_ingest_inventory.json` failure is unrelated, untracked, pre-existing).
- 25 pytest tests pass (`test_derive_temporal_range.py` 23 + `test_emit_completeness_determinism.py` 2).
- `bun run svelte-check` on both `admin/` and `frontend/`: 0 errors.
- `bun test src/contracts/` on the frontend: 14989/0 pass.
- `test_admin_indicators.py` blocked by missing `fastapi` in this venv (pre-existing env state); the rename was applied to the test's `expected_keys` literal and is statically correct.

Deferred from #2:
- `test_admin_indicators.py` re-run once `fastapi` is reinstalled (or in CI).
- Contract (vitest, ajv) one-fixture-per-shape — current `bun test src/contracts/` already validates the regenerated index file against its declared schema (full-corpus check is Tier-B, kept local). A per-shape vitest fixture is optional polish, not landed.

### #2 — Original plan text (preserved for diff)
- Bump [`indicators-completeness.schema.json`](../datasets/schemas/indicators-completeness.schema.json) v1.0 → v1.1 (additive). Rename `last_collected_at` → `last_polled_at` (this IS a breaking rename to a field present today — see migration note below).
- Extend the emitter to consume `derive_temporal_range()` from #1.
- **Determinism test (Gregor's required structural addition):** pytest that runs the emitter twice against an unchanged corpus and asserts byte-identical output of `indicators-completeness.json` (including no spurious wall-clock fields). Pins the §16 #13 / fetched_at-smear lesson at birth.
- **Update [`docs/architecture/backend/coverage.md`](../docs/architecture/backend/coverage.md) in the SAME commit** (Gregor — line 91 becomes a lie the moment the field stops being parsed; can't ship orphaned). Declare: `coverage.temporal` is publisher-owned free-text; yen-gov does NOT parse it; consumers read `rows[].time` (machine) or `indicators-completeness.json` range fields (operator/citizen-vintage).
- Add a CLAUDE.md §10 anti-pattern bullet: "Do not parse `coverage.temporal`. Read `rows[].time` or the completeness-index range fields instead."
- Tests:
  - **Contract (vitest, ajv):** ONE fixture per shape validates against v1.1 (NOT full-corpus per Fowler's tier-calibration catch — full-corpus belongs in Tier B local `python -m yen_gov validate --root .`).
  - **Integration (pytest):** regenerate index, snapshot-diff vs golden to confirm only additive shape change + rename.
- **`last_polled_at` rename migration:** sweep frontend `lib/` and tests for `last_collected_at` references; one-shot rename across producer + consumer + tests in this same commit. No transition window — there is no external consumer of this index yet.

### #3 — Citizen-facing derived caption on indicator card (Level 2) — ✅ SHIPPED 2026-05-17

**What landed (matches the plan below, with one calibrated deviation noted):**

1. **TS mirror of the Python derivation, not just a caption builder.** Added `deriveTemporalRange(rows, indicator) -> TemporalRange | null` to [`frontend/src/lib/indicators.ts`](../frontend/src/lib/indicators.ts) alongside the smaller `buildTemporalCaption` and `cadenceWord` helpers. The plan's stated goal — "no index dependency on the citizen critical path" — required a TS derivation, not just a string-formatter. Both functions are pure (no DOM/Svelte) and vitest-tested.
2. **`buildTemporalCaption({ min_period_label, max_period_label, time_grain?, cadence? }) -> string`** with the planned shapes:
   - multi-period: `{minLabel} → {maxLabel} · {cadenceWord}`
   - single-period: `As of {label} · {cadenceWord}`
   - cadenceWord empty (snapshot date with no publisher cadence): trailing ` · …` segment is dropped.
   - Vocabulary is cadence-first per ADR-0027: `annual / annual (fiscal year) / quarterly / quarterly (fiscal year) / monthly / weekly / daily / every 10 years / irregular updates`. Falls back to `time_grain` mapping when `cadence` is absent.
3. **Cross-language rule-drift guard, shipped as planned.** Shared fixture at [`datasets/_test/temporal-range-fixtures/cases.json`](../datasets/_test/temporal-range-fixtures/cases.json) covers 8 cases (multi-period, single, with-gap, decennial-suppressed, ad_hoc-suppressed, FY tokens, date snapshot, empty rows). BOTH `pytest test_shared_fixture_parity_with_ts_mirror[…]` AND `vitest "deriveTemporalRange (shared-fixture parity with Python)"` parametrize off the same file. A rule drift now fails BOTH suites at the same fixture name.
4. **Validator quietly taught about `datasets/_*/` test subtrees.** `_iter_data_files` in [`backend/yen_gov/validate.py`](../backend/yen_gov/validate.py) now skips any path whose intermediate components start with `_`. Targeted exclusion: it does NOT hide the pre-existing `datasets/ephemeral/_ingest_inventory.json` failure (that filename has `_` but its directory does not). Comment in code spells out the convention.
5. **Citizen surface wired in [`IndicatorChoropleth.svelte`](../frontend/src/lib/IndicatorChoropleth.svelte).** `temporal_caption` $derived sits next to the existing `coverage_summary` / `stale_chip` block; renders as `<p data-testid="indicator-temporal-caption" class="text-[12px] text-slate-700 tabular-nums">` at the top of the under-chart footer (legend, methodology, sources sit below it). Try/catch degrades silently to empty string on heterogeneous-vocabulary adapter bugs (operator surfaces still loud-fail).
6. **Stale comment at L642 removed**, replaced by a comment that points to this plan and explains the new split (coverage row stays; temporal caption is now a sibling).
7. **e2e:** [`frontend/e2e/golden-path.spec.ts`](../frontend/e2e/golden-path.spec.ts) "home renders India map" test now asserts `data-testid="indicator-temporal-caption"` is visible and matches `/(annual|quarterly|monthly|every 10 years|irregular updates|As of)/i`.
8. **Browser smoke (CLAUDE.md §13):** `/t/economy` on `http://localhost:5174/` (5173 was occupied) → 11 caption instances rendered, all of the form `YYYY-04 → YYYY-04 · annual (fiscal year)`. No new console errors beyond a pre-existing benign 404. Cross-route check on `/t/energy` — no regressions.
9. **All tests green:** backend `pytest -q` 526 passed / 3 skipped (ran with `--ignore=test_admin_indicators.py` — fastapi not in local venv, statically correct, CI will run it); frontend `bun test src/lib/indicators.test.ts src/contracts/` 15276 / 0; `bun run svelte-check` 0 errors 5 pre-existing warnings; Tier-B `python -m yen_gov validate --root .` only flags the pre-existing `_ingest_inventory.json`.

**Deferred follow-ups noted while implementing #3:**

- `period_label` is unset on several economy indicators, so the caption reads `2015-04 → 2024-04 · annual (fiscal year)` instead of `FY 2015-16 → FY 2024-25`. The caption derivation correctly falls through to the raw `time` token — the fix belongs upstream in the adapter that owns `period_label`, not in the caption layer. Tracked here so a future indicator-adapter pass can backfill labels and the caption will pick them up unchanged.
- "Last polled" header in [`frontend/src/routes/DataCompleteness.svelte`](../frontend/src/routes/DataCompleteness.svelte) was renamed in the cell binding (Phase #2) but the column heading text is unchanged for now since that page is operator-facing and a future copy pass can revisit the framing in one go.

**Phase #3 review fixes shipped 2026-05-17 (Fowler/Gregor/Max parallel review):**

- **Fowler issue #1 (TS/Python `time_grain` drift).** Python `derive_temporal_range` now writes `time_grain` only when set (`if grain: out["time_grain"] = grain`), matching the TS mirror. Conflating "no grain" with `""` would have drifted between sides and broken any consumer checking `"time_grain" in row`. Added 9th fixture case (`indicator without time_grain omits the key entirely`) that exercises the divergent branch on both sides. `test_missing_time_grain_emits_empty_string` retitled to `test_missing_time_grain_omits_key` and inverted.
- **Fowler issue #2 (`fy`-shape branch never exercised).** Per YAGNI: deleted the entire `"fy"` shape branch from BOTH `backend/yen_gov/inventory/derive.py` AND `frontend/src/lib/indicators.ts`. No production artifact emits `"FY YYYY-YY"` directly in `rows[].time` — fiscal-year artifacts emit ISO-anchored `YYYY-04` with the printable FY label living in `rows[].period_label`. The fy-shape TS code was buggy (`slice(2,6)` mishandled the `"FY 2018-19"` form with space) and the parity fixture never tripped over it. If a future adapter does emit FY-prefixed time tokens, the heterogeneous-vocabulary guard will fail loud rather than silently misparse.
- **Fowler issue #3 (validator `_*/` skip too broad).** Promoted to literal segment match: `_EXCLUDED_PATH_SEGMENTS = frozenset({"_test"})`. Future stray `datasets/_scratch/` or `config/_local/` no longer silently escape Tier B. Added `test_tier_b_skips_test_fixture_subtree_only` proving `_test/` is exempt AND `_scratch/` still fails.
- **Fowler watch-next: silent `catch {}` on citizen surface.** `IndicatorChoropleth.svelte`'s caught caption-derivation error now `console.warn`s with the indicator id — loud enough for a dev with DevTools open, quiet enough that the citizen page keeps rendering.

**Deferred to future arcs (logged here for the next pass; not blocking Phase #4a):**

- **Cadence-vocabulary completeness guard (Gregor #1, Fowler watch-next).** Today the cadence enum lives in 5 places (ADR-0027, indicator schema enum, completeness schema enum, Python `_UNDEFINED_CADENCE`, TS `cadenceWord`). A vitest `for (const v of CADENCE_VALUES) expect(cadenceWord(v, "")).not.toBe("")` would catch the next enum-extension landmine in one fixture row. Wire when the next cadence value is added (probably `quinquennial` per Max).
- **`quinquennial` enum addition (Max coverage gap #1).** NSS/NFHS rounds are ~5-yearly but not on a fixed clock. `decennial` is wrong (too long), `ad_hoc` is wrong (the round system IS planned). Add to ADR-0027 + indicator+completeness schemas + TS union + cadenceWord (wording: `every ~5 years (rounds)`) BEFORE the first NFHS/NSS-round artifact lands — cheaper than retagging.
- **Citizen wording polish (Max wording #1, #2).** `annual (fiscal year)` reads as schema-dump bleed-through — citizen-grade reword is `yearly (Apr–Mar)`. `irregular updates` reads as blame; reword to `released irregularly` or `no fixed schedule`. ~10-line PR with two test updates (vitest assertions + e2e regex widen). Deferred so the cadence-backfill arc can land first and decide all citizen strings in one pass.
- **`indicator.cadence` backfill on remaining 106 artifacts (Max forward work #2).** Only 4-of-110 carry `cadence` today. Without it, the caption falls through to `time_grain` (wrong axis: a `time_grain: year` SRS Bulletin and a `time_grain: year` Census print the same word "annual"). Plan: small `tools/backfill_indicator_cadence.py` walking the catalogue with a switch on `id` prefix. Sequencing per Max: SRS Bulletin (annual), ASI (annual_fy), monthly IIP/CPI, PLFS annual+quarterly_urban, RBI HBS-IS, CAG state finance.
- **Vintage / stale-chip arc (Max vintage signalling).** Pure citizen-side derivation from `(today − parse(maxTime)) > N × cadence_period` (N=2). Uses zero operator data. Renders `· stale` next to the caption when a publisher should have updated but hasn't. Separate arc — don't bundle with wording polish. Needs a `docs/research/` pass on publisher-lag norms (RBI ~9mo, CPI ~2wk, NAS ~14mo) to calibrate N.
- **Test fixtures location (Gregor #2).** `datasets/_test/` sits inside a CLAUDE.md §3 contract surface. Validator skip works, but the directory still signals "test fixtures live in datasets" to a future operator/LLM. Consider moving to top-level `fixtures/` or `tests/fixtures/` with a path-resolution helper on each side. Cheap now, awkward once siblings appear.
- **Rename `inventory/derive.py` (Gregor #3).** Post-ADR-0026 the module name lies — it holds two unrelated derivations (collection_inventory block + temporal range for completeness index) under one `# ===` banner. Rename to `derivations.py` OR split into `collection_inventory.py` + `temporal_range.py` before a third derivation lands.
- **`coverage_summary` cleanup (Hans handover).** Per-indicator framing notes should not repeat the cadence word in prose — it's already in the chart caption.
- **`docs/research/` open follow-ups (Max).** (a) Survey-round publishing cadences (NFHS, NSS, PLFS, SECC, ASI) — actual schedules + slippage history. (b) Publisher lag norms per source family — needed to calibrate the future stale-chip threshold. (c) OWID's own cadence vocabulary as a sanity check.

### #3 — Original plan text (preserved for diff)



### #4a — Retire the markdown coverage report (Level 2, separate PR) — ✅ SHIPPED 2026-05-17

**What landed:**
- Deleted `backend/yen_gov/coverage_indicator_pages.py` (the entire per-indicator markdown emitter — sole remaining consumer of `coverage.temporal`-as-string).
- Deleted `backend/tests/test_coverage_indicator_pages.py` (10 tests).
- Deleted the auto-generated `docs/reference/indicators/` tree (111 markdown files across 9 topics + index).
- Stripped the `coverage_indicator_pages` import + auto-invocation from `coverage` typer command + the standalone `indicator-pages` command in [`backend/yen_gov/cli.py`](../backend/yen_gov/cli.py).
- Updated [`backend/yen_gov/coverage.py`](../backend/yen_gov/coverage.py) `render_markdown` so indicator id cells in `data-inventory.md` are now plain `` `id` `` instead of `[`id`](indicators/<id>.md)` — no more broken links pointing at the deleted tree.
- Rewrote 6 broken `indicators/<topic>/` references in [`docs/reference/data-coverage-report.md`](../docs/reference/data-coverage-report.md) to point at the artifact JSON + citizen `/i/<id>` route + the operator `data-inventory.md § 1`.
- Updated [`docs/architecture/backend/coverage.md`](../docs/architecture/backend/coverage.md) banner to past tense: per-indicator markdown surface retired in Phase #4a (the narrative remainder defers to #4b).
- Updated [`backend/tests/test_coverage.py`](../backend/tests/test_coverage.py) assertion: id cell is plain inline-code, no `(indicators/...)` link target.
- Regenerated `datasets/reference/in/indicators-completeness.json` and `docs/reference/data-inventory.md` from a clean run (no remaining `(indicators/` link targets in the inventory grep-confirmed).

**Verification:**
- `pytest -q` backend: 520 passed (8 fewer than pre-#4a = 10 from deleted `test_coverage_indicator_pages.py` minus 2 net adds elsewhere this session).
- `python -m yen_gov validate --root .`: Tier-A 0 / Tier-B 1 (pre-existing `_ingest_inventory.json missing $schema` only — same as before #4a).
- `python -m yen_gov coverage --write --root .`: writes `data-inventory.md` cleanly, no longer emits the indicator-pages second-half ("`coverage: wrote N files under indicators/`" line is gone).

**Phase #4a review fixes shipped 2026-05-17 (Fowler/Gregor/Hans parallel review):**
- **Topic-doc link sweep (Gregor #1, ship-blocker).** Hand-authored docs at `docs/reference/topics/{energy,fiscal,health,prices}.md` carried 188 `[…](../indicators/<topic>/<id>.md)` links that the tree deletion silently broke. Wrote [`tools/rewrite_retired_indicator_links.py`](../tools/rewrite_retired_indicator_links.py) (idempotent re-runner — keep for future tree moves) and rewrote all 188 to `[…](../../../datasets/indicators/in/<topic>/<id>.json)`. The JSON is now the click-through target — github-browsable, deterministic, and the single source of truth per CLAUDE.md §5.
- **Orphan how-to deleted (Fowler #1 + Gregor #2).** `docs/reference/indicator-pages-generation.md` documented the deleted module + tree + CLI command and had four dead links in one doc. Deleted outright.
- **Tombstone redirect at [`docs/reference/indicators/README.md`](../docs/reference/indicators/README.md) (Gregor #5).** Explains the retirement, points readers at `data-inventory.md § 1` (operator overview) and `datasets/indicators/in/<topic>/<id>.json` (definition / methodology / breaks / sources). Soft-lands any external inbound link that lands at the retired path.
- **`/i/<id>` mentions removed (Hans #1, ship-blocker).** The citizen route does not yet exist (no `frontend/src/routes/i/` directory; the topic-page fallback in [`IndicatorCard.svelte`](../frontend/src/lib/IndicatorCard.svelte) literally comments `// Link to the topic page until /i/<indicator> exists`). My doc copy in `data-coverage-report.md` and `coverage.md` initially pointed at it four times — every reference rewritten to point at the artifact JSON instead.
- **Inventory id-cells link to the JSON artifact (Hans #3 + Fowler #2 + Gregor #5).** `coverage.py::render_markdown` now emits `[`<id>`](../../datasets/indicators/in/<id>.json)` for every id cell in `data-inventory.md` § 1 and § 1Z. An operator scanning the table can now click through to the JSON without hand-constructing paths. Regenerated `data-inventory.md` from a clean run.
- **Test assertion sharpened (Fowler #2).** [`backend/tests/test_coverage.py`](../backend/tests/test_coverage.py) now asserts the positive shape `[`fiscal/national_x`](../../datasets/indicators/in/fiscal/national_x.json)` AND the negative guard `](indicators/` not in md — catches both the original regression (broken link target) and its mirror (id cell deleted entirely).
- **Architecture banner updated** to remove the `/data-completeness` hand-wave (route also doesn't exist yet by that exact path), point at the tombstone, and re-state the #4b deferral in terms of the future citizen-facing per-indicator route.

**Re-verification (after the review fixes):**
- `pytest -q` backend: 520 passed in 49s.
- `python -m yen_gov coverage --write --root .`: writes inventory with linked id cells; `indicators-completeness.json` is byte-unchanged on re-run (determinism preserved).
- `python -m yen_gov validate --root .`: Tier-A 0 / Tier-B 1 (pre-existing only).
- `grep_search '\]\([./]*indicators/[a-z]' docs/**.md`: 0 matches across the whole `docs/` tree.

**Deferred from the #4a review (logged for the next pass; not blocking):**
- **Source-host column in `data-inventory.md` is plain text (Hans #3).** A click-through to `sources[0].url` would be a one-line win in `coverage.py::render_markdown` but requires the scanner to surface the host's source URL alongside (not just the host). Defer to #4b or a dedicated polish pass.
- **Citation hygiene for `series_breaks[]` / `notes[]` / `denominator` (Hans #2).** Until a citizen-facing per-indicator route renders these, they live only inside the JSON. The CPI rebase warning in `prices/national_cpi_iw_index_annual` `notes[]` is the canonical example of transparency a static site should surface. Track as a precondition for closing the parallel-surfaces gap.
- **Stale "Plan" pointer in `docs/reference/topics/*.md` (Fowler defer).** All four topic docs still point at `TODO/PER-INDICATOR-DOCS-PLAN.md` as their "Plan". Link resolves but is stale. Sweep when #4b lands.
- **`coverage.py::_parse_temporal` + `_scan_indicators` + `_row_period_key` schema-drift bug** still live (Gregor #7). Track explicitly in #4b scope.
- **`coverage.py` `span` column could read from the completeness index directly** (Gregor #7). That refactor would let #4b retire `_parse_temporal` without retiring `data-inventory.md`. Useful framing when sequencing #4b.
- **`/memories/repo/`, `docs/agents/`, `.claude/` references to the retired tree (Gregor "one question")** — no inventory taken. Sweep before #4b.
- **Tripwire for #4b (Gregor #4).** "After one cycle" has no operational definition. Pin a concrete trigger (e.g. when a citizen per-indicator route ships and runs for one ingest cycle) in §16 or risk permanent triplication of indicator-depth surfaces.
- **Rationale comment on the id-cell `f"..."` line in `coverage.py` is heavier than needed (Fowler defer).** 6-line block could trim to one. Cosmetic.

### #4b — Retire `coverage.py` and `data-inventory.md` (Level 4, separate PR, separate decision)
- Fowler's split: removing the operator-facing markdown surface is a user-facing decision distinct from removing the parser. Only ship after #4a has been live for one cycle and `/data-completeness` is confirmed to cover the same operator need.
- Out of scope for this plan; documented here as the natural follow-up.

### #5 — Verification (per CLAUDE.md §13)
- `pytest -q` (backend) and `npm test` + Playwright (frontend) all green at every commit boundary.
- Manual UI smoke at `http://localhost:5173/` on one indicator page: caption renders, console clean.
- Confirm `coverage.temporal` is still emitted byte-identically in all 110 artifacts (no accidental re-write).
- Confirm `indicators-completeness.json` regen is byte-identical on a second run (determinism test).

## Sequencing summary

`#1` (pure extract + parser delete) → `#2` (schema bump + emitter + atomic docs + rename) → `#3` (citizen caption) → `#4a` (retire markdown) → `#4b` (retire `coverage.py` + `data-inventory.md`, separate decision).

Each is its own commit/PR. #1+#2 may land on a single feature branch but should be two reviewable commits (Fowler's structural/behavioural split rule).

## Out of scope (explicit)

- Touching `coverage.temporal` content in any artifact. Publisher caption stays exactly as-is.
- Normalising publisher period vocabularies (CLAUDE.md §10 forbids).
- Schema bump on `indicator.schema.json` — not needed.
- Removing the air-quality 2020-gap prose. The note IS load-bearing for the AQ series; it stays.

## Resolved questions (debate outcomes)

| # | Question | Resolution | Reasoning |
|---|---|---|---|
| 1 | Mixed-vocab fail-loud vs silent omit | **Fail loud** at the emitter | Unanimous: overloads null signal (Gregor), hides adapter bug (Fowler), breaks comparability (Max) |
| 2 | Citizen caption: rows[] vs index | **Recompute from rows[]**, share rule via fixture | Fowler: coupling > duplication; keep index off the citizen critical path. Rule-drift policed by a shared JSON fixture exercised by both vitest and pytest |
| 3 | Retire `coverage.py` entirely | **Split:** #4a retires markdown report, #4b (separate PR) decides on `coverage.py` + `data-inventory.md` | Fowler's strangler-fig; user-facing decision separate from parser deletion |
| 4 | `last_collected_at` semantic fix | **Defer the upstream `Last-Modified` work; RENAME now to `last_polled_at`** | Max: rename kills the temptation to display as freshness; true fix needs separate arc per §16 #13 lesson |

## New questions surfaced by the debate (deferred)

- **`entity_coverage_ratio`** on completeness index (Max). Cannot compute without `expected_geographies`, which ADR-0026 moved to operator-state overlay. Needs a separate arc that joins index + overlay. Out of scope here.
- **Cross-indicator scout queries** (Max). `time_grain` field on the index (added in #2) is the enabler. Actual scout query UI ("which indicators cover FY24?") is a follow-up.
- **Upstream `Last-Modified` plumbing** for honest data-change time. §16 #13 lesson, separate arc.

## Phase #1.5 — `indicator.cadence` (ADR-0027) — ✅ SHIPPED

Added after Phase #1 spike surfaced eight artifacts where `gap_count_within_range` was technically correct but citizen-misleading (e.g. Census-on-`year` → gap=45). Parallel debate (Fowler/Gregor/Max) converged on Option C: new optional `indicator.cadence` field, distinct from `time_grain`.

What landed:
- New ADR-0027.
- Indicator schema v4.0 → v4.1 (additive: optional `indicator.cadence` enum `{annual_cy, annual_fy, quarterly_cy, quarterly_fy, monthly, weekly, daily, decennial, ad_hoc}`).
- `derive_temporal_range()` reads cadence; omits BOTH `gap_count_within_range` and `observed_periods_within_range` for `decennial`/`ad_hoc` (per Max — asserting them against an inferred cadence misleads). Mirrors `cadence` into output when set.
- 110 artifacts re-stamped to `$schema_version: 4.1` (strict equality invariant).
- 4 unambiguous witnesses retagged: Census×2 (`decennial`), BUR-GHG×2 (`ad_hoc`).
- TS `IndicatorMeta.cadence?` added in `frontend/src/lib/indicators.ts` (per /memories/lessons.md 2026-05-17 #1).
- `docs/architecture/frontend/indicators.md` cross-link added.
- Validation: 23 unit tests pass; all 110 artifacts validate; spike confirms 4 witnesses suppressed, 4 remain (intended audit queue).

## Deferred follow-ups (Phase #1.5 audit queue)

Three artifacts surfaced by the Phase #1 spike with non-zero `gap_count_within_range` that need adapter-level investigation before any citizen-facing surface ships on top of them:

| # | Artifact | Spike output | Suspected resolution | Owner |
|---|---|---|---|---|
| 3 | `economy/india_external_balance_inr_crore` | 2000-04 → 2023-04, 15 obs, gap=9 | **Likely parser bug** — RBI HBS-IS Statement publishes annually; 9 missing fiscal years smells wrong. Open the workbook, confirm row-skipping isn't matching footnote ordinals (per the 2026-05-11 RBI-ingest lesson in `/memories/lessons.md`). | adapter-quality arc |
| 4 | `energy/india_capacity_pipeline_gw` | 2011 → 2031, 20 obs, gap=1 | Mixed historic + NEP forward projections — fundamentally `ad_hoc`. Retag `indicator.cadence: ad_hoc` next CEA ingest. | next CEA pass |
| 8 | `human_development/state_hdi` | 2011-04 → 2017-04, 2 obs, gap=5 | UNDP HDR 2018 subnational table (sparse) vs Global Data Lab annual 2010-2022 (richer). Source decision needed: switch sources, or retag `cadence: ad_hoc`. | Max + adapter author |

These remain visible in the operator-facing completeness index until resolved — that IS the discovery signal driving the audit.

## Smells fixed from v1 of the plan

- v1 #1 was a hairball commit (schema + emitter + new assertion). Split: #1 (pure rule + parser delete), #2 (schema + emitter + docs + rename).
- v1 #2 put caption logic in `.svelte`. Extracted to `lib/indicators.ts::buildTemporalCaption()`.
- v1 test tier said "every entry validates against v1.1" in vitest — that's Tier B (local), not Tier A (CI). Now: one fixture per shape in vitest, full-corpus stays in `python -m yen_gov validate --root .`.
- v1 had no determinism test for the new derived fields — exactly the surface the fetched_at-smear lived on. Added explicitly in #2.
- v1 implied citizen caption shows `last_collected_at`. Removed — citizen sees data-vintage via `maxLabel`; poll-time stays operator-only.
- v1 #3 (docs) shipped two PRs after the parser stopped being used. Folded into #2 to keep docs and contract atomic per Holy Law #4.

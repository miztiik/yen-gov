# Folded Indicator + Collection-Inventory — Final PR Handover

**Created**: 2026-05-17
**Supersedes**: every prior draft on this topic (deleted): `20260516-fetched-at-content-hash-gate-handover.md`, `20260517-fetch-once-freeze-inventory-handover.md`, `20260517-data-card-and-inventory-driven-collection-handover.md`.
**Status**: Locked. Ready to execute. This document is self-contained — the next agent can run the entire PR from this file alone, in a fresh session, without re-reading any conversation history. If anything here is ambiguous, that is a bug in this document — surface it; do not guess.

---

## §0. How to read this document

**Reading order:**
1. §1 — origin story + lessons (what was rejected, why)
2. §2 — locked working contract (10 rules — do NOT relitigate)
3. §3 — scope (goals + non-goals)
4. §4 — commit slate
5. §5 — per-commit deep dive
6. §6 — schema sketches (folded indicator v2.0, universes v1.0)
7. §7 — glossary (paste into `docs/concepts/`)
8. §8 — frontend copy (Hans-authored, paste-ready)
9. §9 — full test list (per CLAUDE.md §15 tiers)
10. §10 — memory updates
11. §11 — files-touched master table
12. §12 — rejected designs archive (read only if tempted to re-propose any of them)
13. §13 — deferred follow-ons (explicit non-goals with rationale)

**You can skip §12 on first read.** Read it only if you find yourself thinking "let's hash the bytes," "let's add a refetch flag," "let's split methodology into a sidecar," or "let's normalise the period strings." §12 explains why we already rejected those.

---

## §1. Origin story and lessons learned

### §1.1 The bug as the user reported it

> "Whenever some indicator or something is downloading, it is changing the timestamp for everything."

Re-running ingest for ONE source caused `fetched_at` churn across many UNRELATED artifacts on disk; `git status` showed dozens of files dirty with only timestamp diffs; re-running `python -m yen_gov coverage` re-stamped every `docs/reference/indicators/**/*.md` with today's date. Citizens reading the page would see a "Last Updated" chip that lied — it tracked "when the operator last ran a CLI," not "when upstream content actually changed."

The root cause is one sentence: **`datetime.now()` leaked into derived-output content.** The fix is structural — remove it. No band-aid layer (hash gate, byte-compare, ETag) addresses the actual bug.

### §1.2 What the codebase actually has today (confirmed by read-only exploration)

- [backend/yen_gov/core/http.py](backend/yen_gov/core/http.py) line 97 — `Fetcher.fetch` stamps `fetched_at = datetime.now(timezone.utc)`. ADR-0003 ([`docs/architecture/decisions/0003-no-fetch-cache.md`](docs/architecture/decisions/0003-no-fetch-cache.md)) says no cache; every fetch hits the network. Therefore every re-run advances `fetched_at` even when upstream returned byte-identical bytes. **This stays as-is** — `core/http.py` is correct in stamping its own response object; the bug is downstream consumers leaking that value into artifact content unconditionally.
- [backend/yen_gov/sources/iced_common/client.py](backend/yen_gov/sources/iced_common/client.py) ~line 169 — same pattern. Also stays.
- [backend/yen_gov/core/io.py](backend/yen_gov/core/io.py) `write_artifact` — unconditional `path.write_text(...)`. No content-equality gate. **Correct as-is** (per rejected design #2 — no byte-compare).
- [backend/yen_gov/coverage.py](backend/yen_gov/coverage.py) line 229 — `generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d")` baked into the coverage artifact every run. **BUG — fix in commit 1.**
- [backend/yen_gov/coverage_indicator_pages.py](backend/yen_gov/coverage_indicator_pages.py) ~line 108 — `_utc_now()` helper writing today's date into every indicator-page footer; unconditional `target.write_text(...)` at ~line 519. **BUG — fix in commit 1.**
- [backend/yen_gov/composers/energy_capacity_by_source.py](backend/yen_gov/composers/energy_capacity_by_source.py) ~line 116 — `_union_sources` dedups on `(url, fetched_at)` tuple, so the same URL with a different `fetched_at` appears twice in composed `sources[]`. **BUG — fix in commit 2.**
- [backend/yen_gov/sources/iced_state_wise/ingest.py](backend/yen_gov/sources/iced_state_wise/ingest.py) line 459 — `ts = datetime.now(...)` used in artifact content. **BUG — fix in commit 1.**
- The CLI ([backend/yen_gov/cli.py](backend/yen_gov/cli.py)) has no unified `ingest` command — there are ~9 per-source typer commands (`ingest-iced-state-wise`, etc.) plus `validate`, `coverage`, `indicator-pages`, `run`, `reference`. **Names kept; do not rename in this PR** (per §13 deferred).
- The admin panel ([admin/src/routes/Inventory.svelte](admin/src/routes/Inventory.svelte) + [backend/yen_gov/admin/inventory.py](backend/yen_gov/admin/inventory.py)) has an "Inventory" concept — but it's **election-scoped** (state × event coverage matrix). We **extend** it with a sibling `/admin/inventory/indicators` endpoint; we do NOT rename it.
- ~106 indicators exist today across 9 topic folders under [datasets/indicators/in/](datasets/indicators/in/) (~45 energy, ~30 fiscal, rest distributed). ~98 are wired via [datasets/reference/in/topic-catalogue.json](datasets/reference/in/topic-catalogue.json).
- 10 indicators have hand-curated `.notes.json` sidecars validating against [datasets/schemas/indicator-notes.schema.json](datasets/schemas/indicator-notes.schema.json) (`x-version: "1.1"`). **In commit 6 we MERGE these sidecars' content into the parent indicator's `methodology.notes[]` and DELETE the sidecars + the indicator-notes schema.**
- [datasets/schemas/indicator.schema.json](datasets/schemas/indicator.schema.json) is at `x-version: "1.5"`. **Major bump to `2.0` in commit 3** (additive sections — see §6.1).
- CEA installed-capacity adapter ([backend/yen_gov/sources/cea_installed_capacity/](backend/yen_gov/sources/cea_installed_capacity/)) reads operator-dropped xlsx from `.runtime/raw/cea/`. **Kept as-is** — xlsx is throwaway debug per ADR-0003; if the operator loses the file, they re-download from CEA's portal. Not in scope for redesign.
- The frontend has NO citizen-facing source list on per-indicator pages today. Provenance lives only in auto-generated `docs/reference/indicators/**/*.md`. **Commit 8 adds the citizen-facing source list.**

### §1.3 Designs we considered and rejected, in order

The user pushed back repeatedly. Each rejection teaches something. **Do NOT re-propose any of these** without re-reading the rejection reason in §12 (full archive). One-line summaries here for context:

1. SHA-gate at Fetcher + `.meta.json` sidecar — REJECTED: bytes ≠ data; decimal-precision flips defeat hashes.
2. `write_text_if_changed` helper — REJECTED: same hash check in disguise; bandages non-determinism instead of fixing at root.
3. Two-flag refetch (`--refetch --confirm-refetch`) — REJECTED: `rm` IS the force mechanism.
4. Fetcher-level freeze guard — REJECTED: wrong layer. Inventory at the indicator level is the right place to ask "do we have this?".
5. Global `datasets/_inventory.json` — REJECTED: underscore-prefix signals second-class. Inventory is first-class, per-indicator, inline.
6. `fetched_at` → `snapshot_taken` rename — REJECTED: name is fine; glossary fixes meaning.
7. Structured `reference_period` (ISO 8601 interval) — REJECTED: heuristic conversion is lossy; publisher's free-text IS the truth.
8. Partial Max backfill (15-20 indicators) — REJECTED: creates silent two-tier quality. **Resolution: all 106 migrate in one commit; methodology hand-authored where team has knowledge, empty arrays elsewhere, dashboard flags stubs loudly.**
9. Per-indicator `.data-card.json` sidecar — REJECTED: smushes lifecycles; user wants methodology, inventory, and data in ONE file (folded model).
10. ISO-8601 normalised `pending_periods[]` — REJECTED 2026-05-17 (Hans+Max+Fowler debate): Indian publisher vocabularies (`as on 31.03.2025`, `Census 2011`, `FY 2024-25`) don't fit cleanly; any normaliser hits the LLM trap; we ship `{label, frequency}` opaque-token round-trip instead.
11. Naming the obligation set `geographic_universe` / `universe` — REJECTED 2026-05-17 (same debate): academic jargon; collision-prone. **Resolution: `expected_geographies` + `expected_periods`.** `coverage.spatial` / `coverage.temporal` survive as editorial-prose siblings.

### §1.4 What we learned (paste into `/memories/lessons.md` as the 2026-05-17 entry — see §10)

1. **Byte equality is not data equality.** Decimal-precision flips, JSON pretty-print reorders, trailing newlines — all flip bytes without changing meaning. Never use hash-equality or byte-compare as the "did this change?" signal at any layer.
2. **The structural fix beats the band-aid.** When you see "re-runs churn timestamps," the fix is to remove the non-determinism (`datetime.now()` in derived outputs), NOT to add a compare-and-skip helper. CLAUDE.md §5 strict.
3. **The filesystem is the cache.** `.runtime/raw/` presence IS the truth. `rm` is the auditable, single-step force-recollect. No flags.
4. **"Refetch" is the wrong word.** Published statistics are immutable; we COLLECT MORE cells over time. The verb is **collect**.
5. **Inventory is first-class and inline.** Folded into the indicator JSON, not a sidecar, not a global underscored file. The user's repeated phrase: "no ceremonies, no extras."
6. **All or none with explicit gaps.** Don't ship schema-for-future + real-data-for-favourites. Auto-generate structural fields for ALL indicators; mark methodology gaps explicitly; surface stubs LOUDLY in the dashboard.
7. **Existing admin "Inventory" is election-scoped.** Don't rename. Extend with a sibling `/admin/inventory/indicators` endpoint.
8. **Indian publisher vocabularies don't normalise cleanly.** `as on 31.03.2025`, `Census 2011`, `FY 2024-25`, `Q3 FY25` — any centralised canonicaliser will reach for an LLM; LLM-in-build-step is a non-deterministic dependency we will regret. **The adapter owns its vocabulary; the planner round-trips labels opaquely; the citizen reads them as-is.**
9. **Citizen is a real consumer of `pending_periods[].label`.** Therefore the adapter MUST write citizen-readable labels — "FY 2024-25" passes; "Q1FY25" fails; "2024-04-01T00:00:00Z" fails. Documentation rule, not validator rule.
10. **Strangler-fig over big-bang for the three-way intersection.** Phase 1 ships intent (`series_spec`); phase 2 lets adapters opt into `source_capability`. Same `{label, frequency}` shape both sides; emit-layer intersection is one set operation; future opt-in is additive.

---

## §2. Working contract (locked rules — do NOT relitigate)

These are user-locked. If you find yourself wanting to change one, STOP and ask. Do not silently relax.

1. **Fetch-once-freeze, app-wide.** A URL is fetched at most once per (URL, pipeline-version). The raw bytes land in `.runtime/raw/<source>/...` (throwaway debug per ADR-0003). The indicator data and `sources[].fetched_at` derive from that fetch.
2. **`rm` is the only force-recollect mechanism.** No flags, no env vars, no config keys. To re-fetch a URL: `Remove-Item .runtime/raw/<source>/<file>`; re-run per-source ingest CLI. Document this in a 5-line how-to.
3. **CLI vocabulary: collect / emit.** Per-source `ingest-*` typer commands keep their names this PR. (Renaming deferred — §13.)
4. **Raw-file presence IS collection state.** No parallel state file, no `.runtime/state.json`, no SQLite registry. The `collection_inventory` block inside each indicator JSON is a **derived view** of `(series_spec) + (data on disk) + (sources[] provenance)`. It does not own state; it reflects it.
5. **Folded model.** ONE file per indicator at `datasets/indicators/in/<topic>/<id>.json` holds `methodology + collection_inventory + series_spec + data + sources`. **NO sidecars.** No `.data-card.json`, no `.notes.json`, no `.meta.json`. The existing `.notes.json` sidecars (10 files) are merged into the parent's `methodology.notes[]` and deleted.
6. **All 106 indicators migrate in one commit.** Structural fields auto-generated (`expected_geographies` from a default-or-override table; `expected_periods` from data presence; `collection_inventory` derived). Methodology fields hand-authored where team has knowledge; empty arrays elsewhere. Dashboard flags stubs loudly. No silent two-tier.
7. **No hash checks, no byte-compare write-skipping.** Fix non-determinism at source (commit 1).
8. **`fetched_at` keeps its name.** Glossary clarifies meaning. No mass rename.
9. **Planner reads only three fields per indicator.** `collection_inventory.frozen`, `collection_inventory.refetch_requested`, `collection_inventory.pending_periods`. Nothing else. `last_collected_at` is informational; `status` is derived on emit; `unavailable_periods` is editorial.
10. **No normaliser anywhere in the period-label path.** Adapter writes `label` in publisher's vocabulary; planner stores, displays, and passes back verbatim; adapter recognises its own label on the return trip. No LLM. No canonical-form transformer. No regex parser. Adapter author writes the `frequency` enum value once when writing the adapter.

---

## §3. Goals and non-goals

### §3.1 Goals (this PR delivers all of these)

1. Re-running an ingest with no upstream changes leaves `git status` clean. (Original bug, fixed structurally — commit 1+2.)
2. Every indicator file carries inline `methodology`, `series_spec`, and `collection_inventory` blocks. All 106. No silent tiers. Schema v2.0 enforces.
3. The 10 existing `.notes.json` sidecars are merged into parent indicators' `methodology.notes[]` and deleted.
4. Citizens see "what data we have, what we don't, why we don't, where it came from" on every per-indicator page and on a global `/data-completeness` route.
5. Admin gets a `/admin/inventory/indicators` panel listing indicators with frozen/refetch-requested/pending counts.
6. Documentation updated end-to-end: new `docs/concepts/folded-indicator.md`, `docs/concepts/collection-inventory.md`, rewritten `About` + `Disclaimer` pages, ADR-0003 amendment, CLAUDE.md §10 cleanup, backend `AGENTS.md` refresh, how-to on `rm` override, lessons-learned memory update.
7. Schema validates end-to-end (Tier A meta-schema; Tier B all 106 indicators conform to v2.0).
8. Tests at all four CLAUDE.md §15 tiers (unit / contract / integration / e2e) cover the bug fixes AND the new schema + loader + UI.

### §3.2 Non-goals (explicitly out — see §13 for full deferred list with rationale)

- Renaming per-source ingest CLI commands.
- Building a unified `collect <indicator>` wrapper command.
- Max's divergence-band methodology document. Schema reserves `divergence` as nullable; methodology lands in a follow-on PR.
- Hand-authoring rich methodology paragraphs for indicators where the team lacks domain knowledge. Empty arrays + dashboard surfacing.
- Adapter `source_capability.available_periods[]` declaration (phase 2 of the strangler-fig three-way intersection).
- Frontend cross-indicator comparison display convention (use `time_grain`, not per-row `label`) — Max-flagged, frontend ADR-level, deferred.
- Treating elections as indicators (separate folded structure stays — elections live under `datasets/elections/` with their own model).
- Tools-directory consolidation (`tools/` scripts stay scattered for this PR).
- CEA xlsx ingest redesign (operator-drops-xlsx workflow preserved).
- A11y / WCAG / ARIA (project-level non-goal per CLAUDE.md §0).
- Production backend, polling, conditional GET, ETag negotiation (working contract §1).

---

## §4. Commit slate

Two-hat discipline (Tidy First / Kent Beck): structural commits never mix with behavioural commits. Each commit independently shippable, testable, reviewable.

| # | Hat | Title | One-liner |
|---|---|---|---|
| 1 | **behavioural** | Remove `datetime.now()` from derived outputs | Structural determinism fix. Kills the original bug at root. |
| 2 | **behavioural** | Composer per-URL dedup | `_union_sources` dedups by URL alone; defensive cleanup of historical accumulated duplicates. |
| 3 | **structural** | Bump `indicator.schema.json` v1.5 → v2.0 + add `universes.json` | Pure schema addition. New sections defined; old indicators not yet migrated. Validator gated behind a per-version switch until commit 6. |
| 4 | **structural** | Add inventory-derivation module | Pure Python module `backend/yen_gov/inventory/`. Computes `collection_inventory` block from on-disk data + series_spec. Unit-tested against fixtures. No CLI wire-up yet. |
| 5 | **behavioural** | Wire derivation into `coverage` CLI; admin `/inventory/indicators` endpoint | `python -m yen_gov coverage` now updates the `collection_inventory` block inline on each indicator file. Admin gets sibling endpoint. |
| 6 | **behavioural** | Migrate all 106 indicators to v2.0 + merge & delete `.notes.json` sidecars | Single mega-commit landing the data migration. Hand-authored methodology overlays added where team has knowledge. |
| 7 | **structural** | Frontend: folded-indicator loader + types | TS types + loader in `frontend/src/lib/indicator.ts` (extended). No UI wire-up yet. |
| 8 | **behavioural** | Frontend: "About this data" section + `/data-completeness` route + admin indicators panel | Wires loader into existing indicator components; new public route; new admin panel. UI verification per CLAUDE.md §13. |
| 9 | **behavioural** | Docs + memory + ADR + glossary | Closes doc debt per CLAUDE.md §4. |

Commits 1+2 ship the original bug fix. Commits 3-8 deliver folded-indicator + inventory end-to-end. Commit 9 closes doc debt.

**Branch name:** `feature/folded-indicator-inventory`

---

## §5. Per-commit deep dive

### §5.1 Commit 1 — Remove `datetime.now()` from derived outputs

**Files modified:**
- [backend/yen_gov/coverage.py](backend/yen_gov/coverage.py) — line 229: replace `generated_at=datetime.now(...).strftime("%Y-%m-%d")` with `generated_at=_max_input_mtime_date(input_paths)`. New helper at top: walks input paths, returns `max(Path.stat().st_mtime)` formatted as date.
- [backend/yen_gov/coverage_indicator_pages.py](backend/yen_gov/coverage_indicator_pages.py) — DELETE `_utc_now()` helper. DELETE every footer line that says `**Last Updated**: <today>`. Replace with `**Source artifact last modified**: <derived from input mtimes>`.
- [backend/yen_gov/sources/iced_state_wise/ingest.py](backend/yen_gov/sources/iced_state_wise/ingest.py) line 459 — `ts = datetime.now(...)` → `ts = response.fetched_at` (use the per-response `fetched_at`, not a fresh `now()`).
- Audit and fix any other site in `backend/yen_gov/sources/**/ingest.py` or `backend/yen_gov/composers/**/*.py` where `datetime.now()` is written into artifact CONTENT (not logs, not pipeline metadata).

**Files NOT modified (these `datetime.now()` calls are correct — operational telemetry, not content):**
- `backend/yen_gov/core/http.py` — `Fetcher.fetch` stamps the response object's `fetched_at`. Downstream consumers decide whether to surface it.
- `backend/yen_gov/core/logging.py` — log line timestamps.
- `backend/yen_gov/admin/pipeline.py`, `backend/yen_gov/admin/eci_recon.py` — pipeline run metadata.
- `tools/**` build scripts.

**Tests:** [backend/tests/test_coverage_idempotent.py](backend/tests/test_coverage_idempotent.py) (new) — fixture artifact tree → `coverage.write_report(...)` → snapshot bytes + mtime_ns of every output → sleep 1.1s → re-run → assert byte-identical AND mtime_ns unchanged.

**Smoke check:** after committing, `python -m yen_gov coverage; git status` reports clean. Run twice; second run produces no diff.

### §5.2 Commit 2 — Composer per-URL dedup

**File:** [backend/yen_gov/composers/energy_capacity_by_source.py](backend/yen_gov/composers/energy_capacity_by_source.py) — `_union_sources` ~line 116-133.

**Fix:** dedup by `src["url"]` alone (not `(url, fetched_at)`). For each URL, keep the entry with the earliest `fetched_at`. Sort result by URL for deterministic output. See §12 for why earliest (not latest).

**Test:** extend [backend/tests/test_energy_capacity_composer.py](backend/tests/test_energy_capacity_composer.py) — three input docs with same URL and different `fetched_at` → exactly one entry in result, `fetched_at` is the earliest.

### §5.3 Commit 3 — Schema v2.0 bump + universes.json

**Files modified:**

#### [datasets/schemas/indicator.schema.json](datasets/schemas/indicator.schema.json) — v1.5 → v2.0

**Major bump rationale:** new required top-level sections (`series_spec`, `collection_inventory`). Existing indicators don't have them yet; validator emits a clear error pointing at the migration commit. Migration runs in commit 6.

Add to `x-changelog`:
```json
{
  "version": "2.0",
  "date": "2026-05-17",
  "description": "Folded model: methodology + series_spec + collection_inventory now live inline on the indicator. Sidecar .notes.json deprecated and merged into methodology.notes[]. series_spec.expected_geographies + expected_periods declare intent; collection_inventory derives state from on-disk data."
}
```

New required top-level keys (added to existing schema, additive within the document but a major bump because consumer contract changes):
- `methodology` (object) — see §6.1.
- `series_spec` (object) — see §6.1. Contains `expected_geographies` + `expected_periods`.
- `collection_inventory` (object) — see §6.1. Six fields: `status`, `frozen`, `last_collected_at`, `refetch_requested`, `pending_periods`, `unavailable_periods`.

Existing top-level keys (`coverage.spatial`, `coverage.temporal`, `data`, `sources`, `$schema`, `$schema_version`, etc.) retained unchanged. `coverage.*` keeps its existing role as editorial-prose siblings to the new structured `expected_*` fields.

#### [datasets/schemas/indicator-notes.schema.json](datasets/schemas/indicator-notes.schema.json) — UNCHANGED in this commit

Deletion deferred to commit 6 (after sidecar content is merged into parents).

#### [datasets/schemas/universes.schema.json](datasets/schemas/universes.schema.json) — NEW (`x-version: "1.0"`)

Validates the lookup table for "named sets of geo codes."

#### [datasets/reference/in/universes.json](datasets/reference/in/universes.json) — NEW

Named geo-code sets, `$ref`-able from `series_spec.expected_geographies`. Inline arrays also allowed; this file is convenience only (user direction: keep, no deletion ceremony). Initial entries:
- `all_states_and_uts` (36 geo codes)
- `states_only_no_ut` (28)
- `union_only` (`["IN"]`)
- `pre_2014_states_only` (29 — pre-bifurcation Andhra Pradesh).

Add more entries opportunistically in commit 6 if migration reveals additional natural sets.

**Validator switch:** add a per-version conformance gate in [backend/yen_gov/validate.py](backend/yen_gov/validate.py) (or wherever Tier B validation lives). Until commit 6 lands, indicators at `$schema_version: "1.5"` validate against the v1.5 portion of the schema (the new sections are checked only when `$schema_version: "2.0"` is declared). This lets commits 3-5 land without breaking existing 1.5 indicators. Commit 6 removes the switch.

**Tests:**
- [backend/tests/test_indicator_schema.py](backend/tests/test_indicator_schema.py) (extend or new) — Tier A meta-validation of v2.0 schema.
- [backend/tests/test_universes_schema.py](backend/tests/test_universes_schema.py) (new) — Tier A + Tier B for universes.
- [backend/tests/test_validate.py](backend/tests/test_validate.py) (extend) — assert per-version gate works: v1.5 file passes; v2.0 file missing required new sections fails with helpful error.

### §5.4 Commit 4 — Inventory derivation module

**New module:** `backend/yen_gov/inventory/`

```
backend/yen_gov/inventory/
  __init__.py
  derive.py             # derive_collection_inventory(indicator_dict, raw_dir) -> dict
  detect_cells.py       # walk indicator.data, return set of (geo, period_label) cells present
  diff_expected.py      # given series_spec + collected cells, compute pending_periods[]
  overlay.py            # load methodology overlay JSON (hand-authored caveats / breaks / notes)
```

**`derive.py` algorithm (pure function, deterministic — same input → same output bytes):**

1. Read indicator's existing `data` block. Extract set of `(geo, period_label)` cells present.
2. Read `series_spec.expected_geographies` (inline array OR resolve `$ref` against universes.json) and `series_spec.expected_periods` (array of `{label, frequency}`).
3. Compute `pending_periods` = `expected_periods` × `expected_geographies` minus collected cells minus `unavailable_periods` entries. Group by period: a period is "pending" if ANY expected (geo, period) cell is missing. Emit one `{label, frequency}` entry per pending period.
4. `status` derived: `"complete"` if `pending_periods == []` AND `unavailable_periods == []`-or-explained; `"partial"` if any pending; `"empty"` if zero collected.
5. `last_collected_at` derived: max of `sources[].fetched_at` across the indicator's `sources` array. If `sources` is empty, omit field (or null).
6. `frozen` and `refetch_requested` preserved from existing values on the indicator file. (Operator-set; never derived. Default both `false`.)
7. `unavailable_periods` preserved from existing values (operator-set; never derived). Default `[]`.

**Tests:** [backend/tests/test_inventory_derive.py](backend/tests/test_inventory_derive.py) (new):
- `test_derive_against_fixture_complete_series` — all cells present → `status: "complete"`, `pending_periods == []`.
- `test_derive_partial_series_lists_pending` — 10 of 36 states present for one period → that period appears in `pending_periods` with correct `frequency`.
- `test_derive_is_deterministic` — twice on same input → byte-identical output.
- `test_derive_preserves_operator_flags` — input has `frozen: true, refetch_requested: true` → output preserves both.
- `test_derive_status_states` — exercise complete / partial / empty.

### §5.5 Commit 5 — Wire derivation into CLI + admin endpoint

**Backend:**
- [backend/yen_gov/cli.py](backend/yen_gov/cli.py) — extend `coverage` command: after existing report write, walk all indicator data files; for each, call `inventory.derive.derive_collection_inventory(...)`; write the updated `collection_inventory` block back into the indicator file (preserving the rest of the file byte-for-byte modulo the inventory block).
- [backend/yen_gov/coverage.py](backend/yen_gov/coverage.py) — orchestrate the loop; log count of indicators updated, count with status=complete/partial/empty.
- [backend/yen_gov/admin/inventory.py](backend/yen_gov/admin/inventory.py) — ADD `/admin/inventory/indicators` GET endpoint. Returns JSON list of `{indicator_id, topic, status, frozen, refetch_requested, pending_count, last_collected_at}` for all indicators. Existing `/admin/inventory/*` election endpoints unchanged.

**Determinism guarantee:** with commit 1 + commit 4 in place, re-runs produce byte-identical `collection_inventory` blocks → no `git status` churn.

**Test:** [backend/tests/test_coverage_emits_inventory.py](backend/tests/test_coverage_emits_inventory.py) (new) — fixture tree with 3 indicators (already at v2.0) → run `coverage` → assert each indicator file's `collection_inventory` block matches expected → re-run → assert byte-identical.

### §5.6 Commit 6 — Migrate all 106 indicators + delete sidecars

**Volume commit. Single PR-review event.**

**Steps:**
1. Hand-author `backend/yen_gov/inventory/methodology_overlay.json` — keyed by `indicator_id`. Sparse: ~10-20 indicators where team has domain knowledge (RBI Handbook, CAG state accounts, ECI parsing notes, ICED data-quality caveats). Schema-validated.
2. Hand-author `backend/yen_gov/inventory/expected_geographies_overrides.json` — ~20 entries for indicators whose geographies are not the default `all_states_and_uts`. Default applied otherwise.
3. Run a one-shot migration script (`tools/migrate_indicators_v15_to_v20.py`, written for this commit; can stay in `tools/` afterwards as a reference): for each indicator file, add `methodology`, `series_spec`, `collection_inventory` sections per overlays + derived defaults; bump `$schema_version` to `"2.0"`.
4. For each of the 10 indicators with a sibling `.notes.json` sidecar: read sidecar, merge `notes[]` into parent's new `methodology.notes[]`, delete sidecar.
5. Delete `datasets/schemas/indicator-notes.schema.json`. Remove its validator hook.
6. Remove the per-version conformance gate added in commit 3 — all indicators are now v2.0.
7. Run `python -m yen_gov coverage` to populate `collection_inventory` blocks via commit-5 derivation. Verify zero `git status` churn on re-run.
8. Eyeball dashboard counts: how many indicators have empty `methodology_breaks` AND empty `known_caveats`? Expected: ~80. Acceptable — they surface loudly on `/data-completeness` (commit 8).
9. `git add datasets/indicators/in/**/*.json backend/yen_gov/inventory/{methodology_overlay,expected_geographies_overrides}.json datasets/schemas/indicator-notes.schema.json` (latter is a delete) — single commit.

**Tests:**
- [backend/tests/test_datasets_integrity.py](backend/tests/test_datasets_integrity.py) (extend) — every indicator file validates against v2.0; every `indicator_id` matches its directory; every `provenance` URL is in parent's `sources[]`; no `.notes.json` files exist under `datasets/indicators/`.

### §5.7 Commit 7 — Frontend loader + types

**Files modified/created:**
- `frontend/src/lib/indicator.ts` (extend or new) — types matching v2.0 schema:
  ```ts
  export type PeriodFrequency = "annual_fy" | "annual_cy" | "quarterly_fy" | "quarterly_cy"
    | "monthly" | "weekly" | "daily" | "decennial" | "ad_hoc";
  export interface PeriodLabel { label: string; frequency: PeriodFrequency; }
  export interface SeriesSpec {
    description: string;
    expected_geographies: string[];        // inline OR resolved $ref
    expected_periods: PeriodLabel[];
  }
  export type InventoryStatus = "complete" | "partial" | "empty";
  export interface CollectionInventory {
    status: InventoryStatus;
    frozen: boolean;
    last_collected_at: string | null;
    refetch_requested: boolean;
    pending_periods: PeriodLabel[];
    unavailable_periods: string[];          // free-text; editorial
  }
  export interface MethodologyBreak { at: string; note: string; }
  export interface IndicatorMethodology {
    definition: string;
    publisher: string;
    publisher_methodology_url: string | null;
    methodology_breaks: MethodologyBreak[];
    known_caveats: string[];
    notes: string[];                         // merged from former .notes.json sidecars
  }
  export interface Indicator {
    $schema: string;
    $schema_version: string;
    indicator_id: string;
    series_spec: SeriesSpec;
    collection_inventory: CollectionInventory;
    methodology: IndicatorMethodology;
    coverage?: { spatial?: string; temporal?: string };  // legacy editorial prose
    data: unknown;
    sources: { url: string; fetched_at: string }[];
  }
  ```
- Loader function `fetchIndicator(path)` — fetches the single JSON; no separate sidecar fetch (folded model).

**Tests:**
- [frontend/src/contracts/datasets-conform.test.ts](frontend/src/contracts/datasets-conform.test.ts) (extend) — validate all v2.0 indicator files against schema using ajv.
- [frontend/src/lib/indicator.test.ts](frontend/src/lib/indicator.test.ts) (extend or new) — loader unit tests: parses sample, asserts shape.

**No UI wire-up in this commit.** Pure structural.

### §5.8 Commit 8 — Frontend rendering + admin panel

**Public frontend:**
- `frontend/src/lib/AboutThisData.svelte` (new) — renders methodology + inventory:
  - **What this measures** — from `methodology.definition`.
  - **Source** — publisher + link to `publisher_methodology_url`.
  - **Coverage** — "X of Y expected cells collected" + per-state status grid.
  - **Pending** — list `pending_periods[].label`. (Citizen reads as-is; no normalisation.)
  - **Unavailable upstream** — list `unavailable_periods[]` (free-text).
  - **Known caveats** — bullet list (hide section if empty).
  - **Methodology breaks** — bullet list (hide if empty).
  - **Notes** — bullet list from `methodology.notes[]` (hide if empty).
  - **Sources** — render `sources[]` URLs + `fetched_at` (citizen-facing source list, new).
- `frontend/src/routes/DataCompleteness.svelte` (new route `/data-completeness`) — table of all 106 indicators with columns: id, topic, status, frozen, refetch_requested, pending count, methodology-completeness flag (stub vs authored). Sortable. Row total at top: "X of 106 indicators fully methodology-authored; Y are stubs."
- Existing indicator components (`IndicatorCard.svelte`, `StateTopic.svelte`, `TopicLanding.svelte`) — insert `<AboutThisData ... />` below the chart.
- Routes registry — add `/data-completeness`.

**Admin panel:**
- `admin/src/routes/Indicators.svelte` (new) — list view backed by `/admin/inventory/indicators` endpoint. Columns: id, status, frozen toggle (read-only display this PR), refetch_requested toggle (read-only this PR), pending count, last_collected_at. Sort + filter. Sibling tab to existing election Inventory.
- `admin/src/lib/api.ts` (or wherever the admin client lives) — add `fetchIndicators()`.
- Existing `Inventory.svelte` (elections) UNCHANGED — sibling tab navigation added.
- `admin/src/routes/Pipeline.svelte`, `EciRecon.svelte` — cosmetic copy fixes: stop leaking `.runtime/` paths in user-visible strings (per CLAUDE.md §10 — `.runtime/` is internal throwaway, not a citizen / operator surface).

**Tests:**
- [frontend/src/lib/AboutThisData.test.ts](frontend/src/lib/AboutThisData.test.ts) (new) — vitest unit: renders with sample, hides empty sections, displays pending labels verbatim (no transformation).
- [frontend/e2e/golden-path.spec.ts](frontend/e2e/golden-path.spec.ts) (extend) — assert "About this data" renders on one representative indicator route.
- [frontend/e2e/data-completeness.spec.ts](frontend/e2e/data-completeness.spec.ts) (new) — Playwright: route loads, no console error, table has ≥100 rows, at least one stub visible.
- [admin/e2e/indicators-panel.spec.ts](admin/e2e/indicators-panel.spec.ts) (new) — Playwright: panel loads, table renders, no console error.

**UI verification per CLAUDE.md §13 (MANDATORY):** before merging this commit:
1. Start frontend (`bun run dev` in `frontend/`, port 5173). Start admin (`bun run dev` in `admin/`, port 5174).
2. `open_browser_page` to `http://localhost:5173/` → one representative indicator route → `/data-completeness`. `read_page` each; confirm no `[error]` console events; confirm "About this data" section renders; confirm pending periods display verbatim.
3. `open_browser_page` to `http://localhost:5174/` → Indicators tab. `read_page`; confirm panel renders; confirm no new 404s.
4. `screenshot_page` one indicator page showing "About this data."
5. Record in commit message: routes verified.

### §5.9 Commit 9 — Documentation + memory + ADR

Required by CLAUDE.md §4 ("A code commit without its rationale doc is incomplete").

**Files created or rewritten:**

1. **`docs/concepts/folded-indicator.md` (new)** — canonical concept doc:
   - What the folded model is (one file: methodology + series_spec + collection_inventory + data + sources).
   - Why folded (rejected sidecar models; lifecycles are one).
   - Schema link.
   - Glossary (paste from §7 of this handover).
   - "As-published fidelity, not correctness" (Hans).
   - Forward-looking: divergence (Max, deferred); adapter `source_capability` (deferred phase 2).

2. **`docs/concepts/collection-inventory.md` (new)** — companion:
   - Six fields, what each means, who writes each (operator / derived / adapter).
   - Planner reads only `frozen` + `refetch_requested` + `pending_periods`.
   - The `{label, frequency}` opaque-token contract (no normaliser).
   - Adapter MUST write citizen-readable labels (the documentation rule from §1.4 lesson #9).
   - `rm` is the only force-recollect; link to the how-to.

3. **`docs/concepts/data-quality.md` (new)** — Hans-authored stance:
   - We re-publish; we don't correct, smooth, impute, estimate.
   - Empty cells stay empty.
   - Gaps are loud, not hidden.

4. **`docs/architecture/decisions/0003-no-fetch-cache.md`** — amend with a "Clarifications 2026-05-17" section:
   - No-cache stance stands.
   - `.runtime/raw/` is throwaway debug; presence is the inventory record.
   - To force re-collection: `rm` the raw file.
   - Folded indicator model lives at a higher layer and does NOT alter this ADR.

5. **`docs/how-to/force-recollect.md` (new, ~30 lines)** — operator runbook for the `rm` flow.

6. **`CLAUDE.md`** — §10 cleanup:
   - Remove any wording about SHA-gates or `.meta.json` sidecars.
   - Add: "Don't propose `write_text_if_changed`-style byte-compare helpers. Bytes ≠ data. Fix non-determinism at source."
   - Add: "Don't propose normalising publisher period vocabularies. Adapter owns its labels; planner round-trips opaquely. See [folded-indicator.md](docs/concepts/folded-indicator.md)."
   - Reference §15 Open Questions: note `source_capability` phase 2 deferred; cross-indicator label display rule deferred.

7. **`backend/yen_gov/AGENTS.md`** — refresh invariants to match §2 working contract.

8. **`README.md`** — top-level: brief mention of folded-indicator model, link to `/data-completeness`, link to concept docs.

9. **`frontend/src/routes/About.svelte`** — rewrite with paste-ready copy from §8.1.

10. **`frontend/src/routes/Disclaimer.svelte`** — rewrite with paste-ready copy from §8.2.

11. **Memory updates** — via `memory` tool. See §10.

---

## §6. Schema sketches

### §6.1 `indicator.schema.json` v2.0 — new sections (additive)

```jsonc
// (Existing v1.5 fields retained: $schema, $schema_version, indicator_id, coverage.{spatial,temporal},
//  data, sources, etc. Below shows only the new required sections added in v2.0.)

"series_spec": {
  "type": "object",
  "additionalProperties": false,
  "required": ["description", "expected_geographies", "expected_periods"],
  "properties": {
    "description": { "type": "string", "minLength": 10 },
    "expected_geographies": {
      "description": "Either an inline array of geo codes (ECI state codes, district LGD codes, or 'IN' for union), OR a {\"$ref\": \"<universes.json#/universes/KEY>\"} reference.",
      "oneOf": [
        { "type": "array", "items": { "type": "string", "minLength": 1 }, "minItems": 1 },
        { "type": "object", "additionalProperties": false, "required": ["$ref"], "properties": { "$ref": { "type": "string" } } }
      ]
    },
    "expected_periods": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["label", "frequency"],
        "properties": {
          "label": {
            "type": "string",
            "minLength": 1,
            "description": "Publisher's exact period string (e.g. 'FY 2024-25', 'as on 31.03.2025', 'Census 2011'). MUST be citizen-readable without unwrapping."
          },
          "frequency": {
            "enum": ["annual_fy", "annual_cy", "quarterly_fy", "quarterly_cy", "monthly", "weekly", "daily", "decennial", "ad_hoc"]
          }
        }
      }
    }
  }
},

"collection_inventory": {
  "type": "object",
  "additionalProperties": false,
  "required": ["status", "frozen", "refetch_requested", "pending_periods", "unavailable_periods"],
  "properties": {
    "status": { "enum": ["complete", "partial", "empty"], "description": "Derived on emit. Do not hand-edit." },
    "frozen": { "type": "boolean", "description": "Operator-set. When true, planner skips this indicator entirely on next collect run." },
    "last_collected_at": {
      "type": ["string", "null"],
      "format": "date-time",
      "description": "Derived: max(sources[].fetched_at). Informational only; planner does not read."
    },
    "refetch_requested": { "type": "boolean", "description": "Operator-set. When true, planner re-runs the bulk for this indicator's source on next collect. Planner clears the flag to false after a successful re-collect." },
    "pending_periods": {
      "type": "array",
      "description": "Derived by adapter: expected_periods × expected_geographies minus collected minus unavailable. Adapter writes; planner reads; planner passes {label,frequency} back to adapter verbatim when requesting collection.",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["label", "frequency"],
        "properties": {
          "label": { "type": "string", "minLength": 1 },
          "frequency": { "enum": ["annual_fy", "annual_cy", "quarterly_fy", "quarterly_cy", "monthly", "weekly", "daily", "decennial", "ad_hoc"] }
        }
      }
    },
    "unavailable_periods": {
      "type": "array",
      "description": "Operator-set free-text. e.g. '2010-11 — Telangana did not separately exist before 2014'. Editorial; visible to citizens; never derived.",
      "items": { "type": "string", "minLength": 5 }
    }
  }
},

"methodology": {
  "type": "object",
  "additionalProperties": false,
  "required": ["definition", "publisher", "methodology_breaks", "known_caveats", "notes"],
  "properties": {
    "definition": { "type": "string", "description": "One-paragraph plain-English definition of what this indicator measures." },
    "publisher": { "type": "string", "description": "Issuing authority. e.g. 'Reserve Bank of India'." },
    "publisher_methodology_url": { "type": ["string", "null"], "format": "uri" },
    "methodology_breaks": {
      "type": "array",
      "description": "Hand-authored. Empty array = 'no breaks documented yet' (NOT 'no breaks exist').",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["at", "note"],
        "properties": {
          "at": { "type": "string", "description": "Free-text period where the break occurred." },
          "note": { "type": "string", "minLength": 10 }
        }
      }
    },
    "known_caveats": {
      "type": "array",
      "description": "Hand-authored. Empty array = 'no caveats documented yet' (NOT 'no caveats exist').",
      "items": { "type": "string", "minLength": 10 }
    },
    "notes": {
      "type": "array",
      "description": "Free-form notes. Merged in from former .notes.json sidecars during v1.5 → v2.0 migration.",
      "items": { "type": "string", "minLength": 1 }
    }
  }
},

"divergence": {
  "description": "Reserved for Max's divergence-band methodology (deferred). Always null in v2.0.",
  "type": "null"
}
```

### §6.2 `universes.schema.json` v1.0 (new)

Validates `datasets/reference/in/universes.json`. Top-level object with `universes` map; each entry has `description`, `geo_codes[]`, `expected_count`. Standard `$schema`, `$schema_version`, `sources` (empty array — hand-authored), `x-version`, `x-changelog`.

### §6.3 `indicator-notes.schema.json` — deleted in commit 6

After sidecar content is merged into parent `methodology.notes[]`.

---

## §7. Glossary (paste verbatim into `docs/concepts/folded-indicator.md`)

> **Folded indicator.** A single JSON file per indicator at `datasets/indicators/in/<topic>/<id>.json` holding `methodology + series_spec + collection_inventory + data + sources` inline. No sidecars.
>
> **Series cell.** A single observation, identified by `(geography, period_label)`. For "state GSDP, annual FY, 2011-12 to 2024-25" with `all_states_and_uts` geographies, the universe is 36 × 14 = 504 cells.
>
> **`series_spec`.** Declares what the series IS — description, expected geographies, expected periods. The editorial source of truth for what we promise to track.
>
> **`expected_geographies`.** Array of geo codes (ECI state codes, district LGD, or `IN`). Inline or `$ref` into [`universes.json`](../../datasets/reference/in/universes.json).
>
> **`expected_periods`.** Array of `{label, frequency}` objects. `label` is the publisher's exact vocabulary ("FY 2024-25", "as on 31.03.2025", "Census 2011"). `frequency` is a fixed enum.
>
> **`collection_inventory`.** Derived + operator-flagged view of where we stand on this indicator. Six fields: `status`, `frozen`, `last_collected_at`, `refetch_requested`, `pending_periods`, `unavailable_periods`.
>
> **`status`.** `complete` (zero pending, zero unexplained gaps) | `partial` (some pending) | `empty` (zero collected). Derived on emit.
>
> **`frozen`.** Operator flag. When true, planner skips this indicator entirely on next collect.
>
> **`last_collected_at`.** Derived: `max(sources[].fetched_at)`. Informational only. Planner does not read.
>
> **`refetch_requested`.** Operator flag. When true, planner re-runs the bulk on next collect, then clears the flag to false.
>
> **`pending_periods`.** Adapter-written array of `{label, frequency}` entries for periods the indicator expects but has not yet collected. Planner stores, displays, and passes back verbatim — never parses or normalises.
>
> **`unavailable_periods`.** Operator free-text. e.g. "2010-11 — Telangana did not separately exist before 2014." Editorial; citizen-visible; never derived.
>
> **`fetched_at`.** Wall-clock time at which yen-gov last successfully read bytes from the listed URL. Operational provenance. NOT a claim about when upstream content changed. Stable across re-runs (fetch-once-freeze).
>
> **Universe.** A named set of geo codes in [`universes.json`](../../datasets/reference/in/universes.json), `$ref`-able from `series_spec.expected_geographies`. Inline arrays also allowed; the universes table is convenience for the common cases.
>
> **Methodology break.** A documented point where the publisher changed definition, base year, geographic boundary, classification, or sampling frame such that pre- and post-break values are not directly comparable. `methodology_breaks: []` means "no breaks documented yet," NOT "no breaks exist."
>
> **Known caveat.** A documented limitation below break threshold but relevant for interpretation. `known_caveats: []` means "no caveats documented yet," NOT "data is caveat-free."
>
> **Stub methodology.** An indicator where `methodology_breaks` AND `known_caveats` are both empty AND `definition` is the default placeholder. The `/data-completeness` view flags stubs so the team can prioritise backfill.
>
> **Divergence.** Reserved (Max-led, deferred). Always `null` in v2.0.
>
> **As-published fidelity, not correctness.** yen-gov publishes exactly what publishers publish. No adjustment, smoothing, imputation, or correction. Errors in the original appear here; we update when the publisher does.
>
> **Adapter ownership of labels.** The adapter is the single authority on its source's period vocabulary. It writes labels in the publisher's own form and recognises them on the return trip. The planner never parses. No normaliser, no LLM, no canonical-form transformer anywhere in the path.

---

## §8. Frontend copy (Hans-authored, paste-ready)

### §8.1 About page (`frontend/src/routes/About.svelte`)

> # About yen-gov
>
> yen-gov publishes Indian governance and statistical data exactly as upstream publishers publish it. We are a re-publisher, not a statistical agency.
>
> ## What you'll find on every indicator
>
> Every indicator carries an **About this data** panel showing:
>
> - **What the publisher measures.** The publisher's definition in plain English.
> - **Who publishes it.** Linked to their own methodology page where available.
> - **Scope.** What this indicator is meant to track — which states, which years.
> - **Coverage.** How much of that scope we've collected, and where the gaps are. We are loud about gaps.
> - **Known caveats.** Documented limitations.
> - **Methodology breaks.** Points where the publisher changed definition, base year, or geography — so cross-period comparisons stay honest.
> - **Sources.** Exact URLs with timestamps.
>
> Indicators where we haven't yet documented methodology are flagged visibly. See `/data-completeness` for the full inventory.
>
> ## What we don't do
>
> - We do not adjust, smooth, impute, or correct published data. Publisher errors appear here; we update when the publisher does.
> - We do not estimate. Missing cells are marked **pending** or **unavailable upstream** — never filled in.
> - We do not maintain a live API. The site is a static snapshot; we collect periodically and ship a new bundle.
>
> ## Trust, in one sentence
>
> Trust the data exactly as far as you trust the publisher. yen-gov's job is to make their data more accessible without changing what they said.

### §8.2 Disclaimer page (`frontend/src/routes/Disclaimer.svelte`)

> # Disclaimer
>
> yen-gov is a faithful re-publisher of government and statistical data from entities including the Reserve Bank of India, the Election Commission of India, the Comptroller and Auditor General, the Ministry of Statistics and Programme Implementation, and others.
>
> **Accuracy.** The figures shown here reflect what the listed publishers published at the time we collected them. We do not independently verify, correct, or estimate any figure. Errors in the original publication appear here; we update when the publisher updates.
>
> **Completeness.** Many indicators are partially collected. We mark missing cells as **pending** (upstream expected to publish) or **unavailable upstream** (publisher does not separately report this geography or period). Empty cells are never filled with estimates.
>
> **Methodology.** Many indicators have methodology breaks, base-year revisions, geographic-boundary changes, or definitional shifts over time. Where we have documented these, they appear on the indicator's About this data panel. Absence of a documented break does NOT mean none exists — only that we have not yet documented it. See `/data-completeness`.
>
> **Citation.** When citing yen-gov, please also cite the underlying publisher. yen-gov is a routing layer, not a primary source.
>
> **Corrections.** Spotted an error in our presentation? File an issue. Spotted an error in the data itself? Contact the original publisher; we update once they publish a correction.

---

## §9. Tests required (full list per CLAUDE.md §15)

### Backend (pytest)

1. `backend/tests/test_coverage_idempotent.py` (new) — re-run produces byte-identical output (commit 1).
2. `backend/tests/test_energy_capacity_composer.py` (extend) — `_union_sources` dedups by URL, keeps earliest `fetched_at` (commit 2).
3. `backend/tests/test_indicator_schema.py` (new or extend) — Tier A meta-validation v2.0 (commit 3).
4. `backend/tests/test_universes_schema.py` (new) — Tier A + Tier B universes (commit 3).
5. `backend/tests/test_validate.py` (extend) — per-version gate works during transition (commit 3); gate removal verified (commit 6).
6. `backend/tests/test_inventory_derive.py` (new) — derivation determinism, pending detection, status states, operator-flag preservation (commit 4).
7. `backend/tests/test_coverage_emits_inventory.py` (new) — CLI integration, byte-identical re-runs (commit 5).
8. `backend/tests/test_admin_inventory_indicators.py` (new) — `/admin/inventory/indicators` endpoint returns expected shape (commit 5).
9. `backend/tests/test_datasets_integrity.py` (extend) — all 106 v2.0; no `.notes.json` files survive; provenance cross-check (commit 6).

### Frontend (vitest)

10. `frontend/src/contracts/datasets-conform.test.ts` (extend) — all v2.0 indicators validate (commit 7).
11. `frontend/src/lib/indicator.test.ts` (extend or new) — loader parses v2.0 shape (commit 7).
12. `frontend/src/lib/AboutThisData.test.ts` (new) — renders, hides empty sections, displays pending labels verbatim (commit 8).

### Frontend e2e (Playwright)

13. `frontend/e2e/golden-path.spec.ts` (extend) — "About this data" renders; one provenance assertion (commit 8).
14. `frontend/e2e/data-completeness.spec.ts` (new) — route loads, table ≥100 rows, ≥1 stub visible, no console error (commit 8).

### Admin e2e (Playwright)

15. `admin/e2e/indicators-panel.spec.ts` (new) — panel loads, table renders, no console error (commit 8).

**All must be green at PR merge** (CLAUDE.md §9).

---

## §10. Memory updates (`/memories/`)

### §10.1 PREPEND to `/memories/lessons.md` (keep all prior entries):

```
Lesson (2026-05-17, yen-gov folded-indicator + collection-inventory):

Landed on a folded model — one JSON per indicator carrying methodology + series_spec + collection_inventory + data + sources inline. NO sidecars. Schema bumped v1.5 → v2.0 (major); the 10 existing `.notes.json` sidecars merged into parent `methodology.notes[]` and deleted in the migration commit.

Rejected designs (do NOT re-propose; full archive in TODO/20260517-folded-indicator-and-collection-inventory-handover.md §12):
1. SHA-gate at Fetcher + .meta.json sidecar — bytes ≠ data.
2. write_text_if_changed helper — same hash check in disguise.
3. Two-flag refetch — rm IS the force mechanism.
4. Fetcher freeze-guard — wrong layer.
5. Global _inventory.json — underscore signals second-class; inventory is first-class inline.
6. fetched_at rename — name is fine; glossary fixes meaning.
7. Structured ISO reference_period — heuristic; lossy.
8. Partial Max backfill — creates silent two-tier; all-or-none rule.
9. Per-indicator .data-card.json sidecar — smushes lifecycles; fold instead.
10. ISO-normalised pending_periods[] — Indian publisher vocabularies (`as on 31.03.2025`, `Census 2011`, `FY 2024-25`) don't fit; any normaliser hits the LLM trap; ship `{label, frequency}` opaque-token round-trip.
11. `geographic_universe` / `universe` naming — academic jargon, collision-prone. Resolved: `expected_geographies` + `expected_periods`.

Key principles forced by the design loop:
- **Adapter owns its source's vocabulary; planner round-trips opaquely; citizen reads as-is.** No normaliser anywhere. Adapter MUST write citizen-readable labels (doc rule, not validator rule).
- **Inventory derived, not stored separately.** `collection_inventory` block reflects (series_spec + data on disk + sources). No parallel state file.
- **Planner reads exactly three fields per indicator:** `frozen`, `refetch_requested`, `pending_periods`. Discipline forces minimal coupling.
- **Strangler-fig for the three-way intersection.** Phase 1: `series_spec` is the authority; emit-layer assumes adapter covers it. Phase 2 (deferred): adapter optionally declares `source_capability.available_periods[]`; emit-layer intersects; residue → `unavailable_upstream` with adapter-supplied reason.
- **Structural fix beats band-aid.** "Re-runs churn timestamps" → remove `datetime.now()` from derived outputs, not add compare-and-skip helpers. CLAUDE.md §5 strict.
- **The 7 personas debate, not monologue.** When stuck on naming/format/scope tradeoffs, run a real Hans+Max+Fowler three-round debate — they reach convergence the single-voice analysis misses (e.g. Max's "expected_*" beat Hans's "scope" beat Fowler's neutral lean).

---
```

(Prior 2026-05-16 SHA-gate lesson and all earlier entries STAY below.)

### §10.2 Update `/memories/repo/yen-gov-architecture.md`:

Append:

```
## Folded indicator + collection-inventory model (2026-05-17, PR #N)

- Every indicator at datasets/indicators/in/<topic>/<id>.json is a single folded file: methodology + series_spec + collection_inventory + data + sources.
- Schema: datasets/schemas/indicator.schema.json @ x-version 2.0.
- Geography sets: datasets/reference/in/universes.json (convenience; inline arrays also allowed).
- Derivation: backend/yen_gov/inventory/derive.py. Wired into `python -m yen_gov coverage`.
- Hand-authored overlays: backend/yen_gov/inventory/methodology_overlay.json + expected_geographies_overrides.json (sparse).
- Frontend: AboutThisData.svelte on every indicator page; /data-completeness route.
- Admin: /admin/inventory/indicators endpoint + Indicators.svelte panel (sibling to existing election Inventory).
- Fetch-once-freeze working contract: CLAUDE.md §10. rm is the only force-recollect.
- Adapter owns period-label vocabulary. Planner round-trips {label, frequency} opaquely. No normaliser, no LLM.
- Planner reads only: frozen, refetch_requested, pending_periods.
- Sidecar .notes.json files deleted in commit 6 migration; content merged into methodology.notes[].
```

---

## §11. Files-touched master table

| Layer | File | Action | Commit |
|---|---|---|---|
| Backend core | `backend/yen_gov/coverage.py` | Modify | 1, 5 |
| Backend core | `backend/yen_gov/coverage_indicator_pages.py` | Modify | 1 |
| Backend core | `backend/yen_gov/cli.py` | Modify | 5 |
| Backend core | `backend/yen_gov/validate.py` (or equivalent) | Modify | 3, 6 |
| Backend sources | `backend/yen_gov/sources/iced_state_wise/ingest.py` | Modify | 1 |
| Backend composers | `backend/yen_gov/composers/energy_capacity_by_source.py` | Modify | 2 |
| Backend inventory | `backend/yen_gov/inventory/__init__.py` | Create | 4 |
| Backend inventory | `backend/yen_gov/inventory/derive.py` | Create | 4 |
| Backend inventory | `backend/yen_gov/inventory/detect_cells.py` | Create | 4 |
| Backend inventory | `backend/yen_gov/inventory/diff_expected.py` | Create | 4 |
| Backend inventory | `backend/yen_gov/inventory/overlay.py` | Create | 4 |
| Backend inventory | `backend/yen_gov/inventory/methodology_overlay.json` | Create | 6 |
| Backend inventory | `backend/yen_gov/inventory/expected_geographies_overrides.json` | Create | 6 |
| Backend admin | `backend/yen_gov/admin/inventory.py` | Modify (add /indicators endpoint) | 5 |
| Backend AGENTS | `backend/yen_gov/AGENTS.md` | Modify | 9 |
| Schemas | `datasets/schemas/indicator.schema.json` | Modify (v1.5 → v2.0) | 3 |
| Schemas | `datasets/schemas/indicator-notes.schema.json` | DELETE | 6 |
| Schemas | `datasets/schemas/universes.schema.json` | Create | 3 |
| Reference data | `datasets/reference/in/universes.json` | Create | 3 |
| Indicators | `datasets/indicators/in/**/*.json` (×106) | Modify (migrate to v2.0) | 6 |
| Indicators | `datasets/indicators/in/**/*.notes.json` (×10) | DELETE | 6 |
| Frontend lib | `frontend/src/lib/indicator.ts` | Modify/extend | 7 |
| Frontend lib | `frontend/src/lib/AboutThisData.svelte` | Create | 8 |
| Frontend routes | `frontend/src/routes/DataCompleteness.svelte` | Create | 8 |
| Frontend routes | `frontend/src/routes/About.svelte` | Modify | 9 |
| Frontend routes | `frontend/src/routes/Disclaimer.svelte` | Modify | 9 |
| Frontend integration | `frontend/src/lib/IndicatorCard.svelte` (etc.) | Modify | 8 |
| Frontend routes registry | `frontend/src/App.svelte` (or equivalent) | Modify | 8 |
| Admin routes | `admin/src/routes/Indicators.svelte` | Create | 8 |
| Admin lib | `admin/src/lib/api.ts` (or equivalent) | Modify (add fetchIndicators) | 8 |
| Admin routes | `admin/src/routes/Pipeline.svelte` | Modify (cosmetic copy fix) | 8 |
| Admin routes | `admin/src/routes/EciRecon.svelte` | Modify (cosmetic copy fix) | 8 |
| Tests backend | `backend/tests/test_coverage_idempotent.py` | Create | 1 |
| Tests backend | `backend/tests/test_energy_capacity_composer.py` | Extend | 2 |
| Tests backend | `backend/tests/test_indicator_schema.py` | Create/extend | 3 |
| Tests backend | `backend/tests/test_universes_schema.py` | Create | 3 |
| Tests backend | `backend/tests/test_validate.py` | Extend | 3, 6 |
| Tests backend | `backend/tests/test_inventory_derive.py` | Create | 4 |
| Tests backend | `backend/tests/test_coverage_emits_inventory.py` | Create | 5 |
| Tests backend | `backend/tests/test_admin_inventory_indicators.py` | Create | 5 |
| Tests backend | `backend/tests/test_datasets_integrity.py` | Extend | 6 |
| Tests frontend | `frontend/src/contracts/datasets-conform.test.ts` | Extend | 7 |
| Tests frontend | `frontend/src/lib/indicator.test.ts` | Create/extend | 7 |
| Tests frontend | `frontend/src/lib/AboutThisData.test.ts` | Create | 8 |
| Tests frontend e2e | `frontend/e2e/golden-path.spec.ts` | Extend | 8 |
| Tests frontend e2e | `frontend/e2e/data-completeness.spec.ts` | Create | 8 |
| Tests admin e2e | `admin/e2e/indicators-panel.spec.ts` | Create | 8 |
| Docs concepts | `docs/concepts/folded-indicator.md` | Create | 9 |
| Docs concepts | `docs/concepts/collection-inventory.md` | Create | 9 |
| Docs concepts | `docs/concepts/data-quality.md` | Create | 9 |
| Docs architecture | `docs/architecture/decisions/0003-no-fetch-cache.md` | Modify (clarifications section) | 9 |
| Docs how-to | `docs/how-to/force-recollect.md` | Create | 9 |
| Docs root | `CLAUDE.md` | Modify (§10 cleanup) | 9 |
| Docs root | `README.md` | Modify | 9 |
| Tools | `tools/migrate_indicators_v15_to_v20.py` | Create | 6 |
| Memory | `/memories/lessons.md` | Prepend (via memory tool) | 9 |
| Memory | `/memories/repo/yen-gov-architecture.md` | Append (via memory tool) | 9 |

---

## §12. Rejected designs archive (read if tempted to re-propose)

| # | Design | Status | Why rejected |
|---|---|---|---|
| 1 | SHA-gate at `Fetcher.fetch` + `.runtime/raw/<path>.meta.json` sidecar storing `{content_sha256, first_fetched_at, etag, last_modified}`. On re-fetch, if body SHA matches, reuse `first_fetched_at`. | REJECTED 2026-05-16 | Hashing every fetch is wasted compute. A decimal-precision flip ($1.00 vs $1.0000), comma vs period decimal separator, trailing-newline change — all flip the hash without changing the data. Hash equality is the wrong signal. Sidecar parallel-registry creates divergence-bug surface. |
| 2 | `write_text_if_changed(path, text)` helper — read existing, byte-compare, skip write if identical. | REJECTED 2026-05-16 | Same hash check in disguise. JSON pretty-print reorder, indent change, trailing newline all look "different" and rewrite. Papers over the real bug (`datetime.now()` leaking into content). CLAUDE.md §5 violation. **Structural fix:** remove `datetime.now()` from derived outputs so re-runs produce byte-identical output by construction. |
| 3 | Two-flag force-refetch (`--refetch --confirm-refetch`). | REJECTED 2026-05-17 | Gimmicky. `rm .runtime/raw/<path>` IS the force mechanism. Filesystem IS the cache. Deletion IS the override. |
| 4 | Fetcher-level freeze guard ("if raw file exists, return cached bytes; never hit network"). | REJECTED 2026-05-17 | Wrong layer. The right question is asked **upstream** by the ingest layer against the inventory: "do we already have data for indicator X period Y?" Fetcher never needs a guard because nothing calls it for already-collected cells. "Refetch" is the wrong word — we COLLECT MORE. |
| 5 | Global `datasets/_inventory.json` (single file listing all collected/pending URLs). | REJECTED 2026-05-17 | Underscore prefix signals "machine-only / second-class." Inventory is first-class, per-indicator, inline. Global rollup hides per-indicator gaps. |
| 6 | Rename `fetched_at` → `snapshot_taken`. | REJECTED 2026-05-17 | "`fetched_at` is not a terrible name" (user verbatim). Glossary fixes meaning, not a mass rename. |
| 7 | Structured `reference_period` field (ISO 8601 interval). | REJECTED 2026-05-17 | Requires heuristic conversion. Lossy. No consumer needs structure. Publisher's free-text IS the truth. |
| 8 | Partial Max backfill (data-card for 15-20 indicators, rest unauthored). | REJECTED 2026-05-17 | Silent two-tier quality. "All or none." **Resolution:** auto-generate structural fields for ALL 106; methodology hand-authored where known, empty arrays elsewhere, dashboard flags stubs loudly. |
| 9 | Per-indicator `.data-card.json` sidecar. | REJECTED 2026-05-17 | Smushes lifecycles. User: "no sidecars, no extras, no ceremonies." Fold methodology + inventory inline. |
| 10 | ISO-8601-normalised `pending_periods[]`. | REJECTED 2026-05-17 (Hans+Max+Fowler debate) | Indian publisher vocabularies (`as on 31.03.2025`, `Census 2011`, `FY 2024-25`, `Q3 FY25`) don't fit cleanly. Any normaliser will reach for an LLM. LLM-in-build-step is non-deterministic dependency we will regret. **Resolution:** `{label, frequency}` opaque-token round-trip; nothing parses; adapter owns vocabulary end-to-end. |
| 11 | `geographic_universe` / `universe` field naming. | REJECTED 2026-05-17 (Hans+Max+Fowler debate) | Academic jargon. No international-catalogue precedent (FRED uses `geo`/`time_period`; OWID uses `dimensions`; Eurostat uses `geo`/`time_period`). Collision-prone with future fields. **Resolution:** `expected_geographies` + `expected_periods` — explicit obligation, citizen-readable, hard to want elsewhere. `coverage.spatial` / `coverage.temporal` keep their role as editorial-prose siblings. |

For composer dedup `(url, fetched_at) → url`: keep **earliest** `fetched_at` because it's the more conservative claim about "when we first saw this URL." With fetch-once-freeze enforced from commit 1 onwards, all entries for a URL share one `fetched_at` anyway; the earliest-keep rule is defensive cleanup of historical duplicates already on disk.

---

## §13. Deferred follow-ons (explicit non-goals, rationale documented)

These are intentionally NOT in this PR. Each has a rationale. None are blockers.

1. **Adapter `source_capability.available_periods[]` declaration** (phase 2 of three-way intersection). Strangler-fig: this PR's emit layer assumes adapters cover full `series_spec`; future PR lets adapters opt in to declaring capability, emit-layer intersects three sets, residue → `unavailable_upstream` with adapter-supplied reason. Same `{label, frequency}` shape both sides.
2. **Frontend cross-indicator comparison display convention.** When chart pulls from multiple indicators with different label vocabularies, display the indicator's `frequency` value rather than per-row `label`. Max-flagged in the debate. Frontend ADR-level decision. Not a schema change.
3. **Max's divergence-band methodology.** Schema reserves `divergence` as nullable in v2.0. Methodology + bands authored in a follow-on PR.
4. **Unified `collect <indicator>` CLI wrapper.** Per-source `ingest-*` typer commands keep their names. Wrapper deferred until indicator-keyed planner UI lands.
5. **Renaming per-source CLI commands.** Out of scope; high churn risk; cosmetic.
6. **Elections-as-indicators.** Elections live under `datasets/elections/` with their own model. Folding them into the indicator schema is a separate design conversation.
7. **`tools/` directory consolidation.** ~50 scripts scattered with mixed quality. Triage and consolidation deferred.
8. **CEA xlsx ingest redesign.** Operator-drops-xlsx workflow under `.runtime/raw/cea/` preserved as-is. If xlsx lost, operator re-downloads from CEA portal.
9. **Global `coverage.py` rollup output replacement.** [docs/reference/data-inventory.md](docs/reference/data-inventory.md) survives this PR (with the `datetime.now()` footer removed in commit 1). Future PR may replace with view-time aggregation of `collection_inventory` blocks.
10. **Operator write-actions on admin Indicators panel.** This PR ships read-only display. Toggling `frozen` / `refetch_requested` from the UI requires write endpoints + auth model; deferred.
11. **Issue-template for citizen-reported data errors.** Mentioned in `Disclaimer.svelte` copy ("File an issue"); template setup deferred.

---

## §14. Pre-flight checklist (before opening the PR)

- [ ] All 9 commits made; two-hat discipline preserved (structural ≠ behavioural).
- [ ] `pytest -q` green in `backend/`.
- [ ] `npm test` green in `frontend/`.
- [ ] `npm run test:e2e` green in `frontend/`.
- [ ] `npm run test:e2e` green in `admin/` (if e2e command exists; otherwise smoke-tested per §13).
- [ ] `python -m yen_gov coverage; git status` → clean (commit 1 + commit 5 working as designed).
- [ ] Re-run `python -m yen_gov coverage` immediately again → still clean.
- [ ] No `[DEBUG]` markers in code (CLAUDE.md §7).
- [ ] No new hardcoded magic strings/numbers (CLAUDE.md §6, §10).
- [ ] No new mocks beyond the rare ones explicitly listed in CLAUDE.md §15.
- [ ] `bun install` run in `frontend/` AND `admin/` if either `package.json` touched; both `bun.lock` files staged in the same commits (CLAUDE.md §9).
- [ ] Browser-tool UI verification done per CLAUDE.md §13; routes verified noted in commit 8 message.
- [ ] Memory files updated (`/memories/lessons.md` prepended, `/memories/repo/yen-gov-architecture.md` appended).
- [ ] `docs/concepts/`, `docs/architecture/decisions/`, `docs/how-to/`, `CLAUDE.md`, `README.md`, backend `AGENTS.md` all updated in commit 9.
- [ ] No `.notes.json` files survive under `datasets/indicators/`.
- [ ] `datasets/schemas/indicator-notes.schema.json` deleted.
- [ ] Per-version validator gate (added commit 3, removed commit 6) — confirm removal.
- [ ] PR description summarises: original bug + structural fix; folded model + v2.0 schema; 106 migrations; new public route; new admin panel; explicit deferred list (§13).

---

## §15. Invocation phrase for the next agent

> "Read `TODO/20260517-folded-indicator-and-collection-inventory-handover.md` end-to-end. Execute the 9-commit slate in §4 in order. Honour the 10 working-contract rules in §2 — do NOT relitigate. If anything is ambiguous, surface to user; do not guess. Run the §14 pre-flight checklist before opening the PR."

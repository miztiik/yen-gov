# Folded Indicator + Collection-Inventory — Final PR Handover

**Created**: 2026-05-17
**Supersedes**: every prior draft on this topic (deleted): `20260516-fetched-at-content-hash-gate-handover.md`, `20260517-fetch-once-freeze-inventory-handover.md`, `20260517-data-card-and-inventory-driven-collection-handover.md`.
**Status**: Amended after critical review. Ready to execute **only with §3.3 applied**. §3.3 is authoritative over older wording elsewhere in this handover where they conflict. If anything remains ambiguous, that is a bug in this document — surface it; do not guess.

---

## §0. How to read this document

**Reading order:**
1. §1 — origin story + lessons (what was rejected, why)
2. §2 — locked working contract (10 rules — do NOT relitigate)
3. §3 — scope (goals + non-goals)
4. §3.3 — critical amendments and solution guidelines (authoritative corrections)
5. §4 — amended commit slate
6. §5 — per-commit deep dive, read through the §3.3 corrections
7. §6 — schema sketches (folded indicator v2.0, universes v1.0), read through the §3.3 period model
8. §7 — glossary (paste into `docs/concepts/`)
9. §8 — frontend copy (Hans-authored, paste-ready)
10. §9 — full test list (per CLAUDE.md §15 tiers)
11. §10 — memory updates
12. §11 — files-touched master table
13. §12 — rejected designs archive (read only if tempted to re-propose any of them)
14. §13 — deferred follow-ons (explicit non-goals with rationale)

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
- The admin panel ([admin/src/routes/Inventory.svelte](admin/src/routes/Inventory.svelte) + [backend/yen_gov/admin/inventory.py](backend/yen_gov/admin/inventory.py)) has an "Inventory" concept — but it's **election-scoped** (state x event coverage matrix). We **extend** it with a sibling `/api/inventory/indicators` endpoint and admin shell panel; we do NOT rename the existing election inventory.
- ~106 indicators exist today across 9 topic folders under [datasets/indicators/in/](datasets/indicators/in/) (~45 energy, ~30 fiscal, rest distributed). ~98 are wired via [datasets/reference/in/topic-catalogue.json](datasets/reference/in/topic-catalogue.json).
- 10 indicators have hand-curated `.notes.json` sidecars validating against [datasets/schemas/indicator-notes.schema.json](datasets/schemas/indicator-notes.schema.json) (`x-version: "1.1"`). **In commit 6 we fold these sidecars losslessly into typed inline methodology fields and delete the sidecars; commit 7 deletes the sidecar schema after contraction.**
- [datasets/schemas/indicator.schema.json](datasets/schemas/indicator.schema.json) is at `x-version: "1.5"`. **Expand to `1.6` in commit 3, migrate in commit 6, contract to `2.0` in commit 7** (see §3.3 and §6.1).
- CEA installed-capacity adapter ([backend/yen_gov/sources/cea_installed_capacity/](backend/yen_gov/sources/cea_installed_capacity/)) reads operator-dropped xlsx from `.runtime/raw/cea/`. **Kept as-is** — xlsx is throwaway debug per ADR-0003; if the operator loses the file, they re-download from CEA's portal. Not in scope for redesign.
- The frontend has NO citizen-facing source list on per-indicator pages today. Provenance lives only in auto-generated `docs/reference/indicators/**/*.md`. **Commit 10 adds the citizen-facing source list.**

### §1.3 Designs we considered and rejected, in order

The user pushed back repeatedly. Each rejection teaches something. **Do NOT re-propose any of these** without re-reading the rejection reason in §12 (full archive). One-line summaries here for context:

1. SHA-gate at Fetcher + `.meta.json` sidecar — REJECTED: bytes ≠ data; decimal-precision flips defeat hashes.
2. `write_text_if_changed` helper — REJECTED: same hash check in disguise; bandages non-determinism instead of fixing at root.
3. Two-flag refetch (`--refetch --confirm-refetch`) — REJECTED: `rm` IS the force mechanism.
4. Fetcher-level freeze guard — REJECTED: wrong layer. Inventory at the indicator level is the right place to ask "do we have this?".
5. Global mutable `datasets/_inventory.json` — REJECTED: underscore-prefix signals second-class. Inventory truth is first-class, per-indicator, inline. A generated static public index under `datasets/reference/in/` is allowed.
6. `fetched_at` → `snapshot_taken` rename — REJECTED: name is fine; glossary fixes meaning.
7. Structured `reference_period` (ISO 8601 interval) — REJECTED: heuristic conversion is lossy; publisher's free-text IS the truth.
8. Partial Max backfill (15-20 indicators) — REJECTED: creates silent two-tier quality. **Resolution: all 106 migrate in one commit; methodology hand-authored where team has knowledge, empty arrays elsewhere, dashboard flags stubs loudly.**
9. Per-indicator `.data-card.json` sidecar — REJECTED: smushes lifecycles; user wants methodology, inventory, and data in ONE file (folded model).
10. ISO-8601 normalised `pending_periods[]` — REJECTED 2026-05-17 (Hans+Max+Fowler debate): Indian publisher vocabularies (`as on 31.03.2025`, `Census 2011`, `FY 2024-25`) don't fit cleanly; any normaliser hits the LLM trap; we ship `{key, label, frequency}` period-token round-trip instead.
11. Naming the obligation set `geographic_universe` / `universe` — REJECTED 2026-05-17 (same debate): academic jargon; collision-prone. **Resolution: `expected_geographies` + `expected_periods`.** `coverage.spatial` / `coverage.temporal` survive as editorial-prose siblings.

### §1.4 What we learned (paste into `/memories/lessons.md` as the 2026-05-17 entry — see §10)

1. **Byte equality is not data equality.** Decimal-precision flips, JSON pretty-print reorders, trailing newlines — all flip bytes without changing meaning. Never use hash-equality or byte-compare as the "did this change?" signal at any layer.
2. **The structural fix beats the band-aid.** When you see "re-runs churn timestamps," the fix is to remove the non-determinism (`datetime.now()` in derived outputs), NOT to add a compare-and-skip helper. CLAUDE.md §5 strict.
3. **The filesystem is the cache.** `.runtime/raw/` presence IS the truth. `rm` is the auditable, single-step force-recollect. No flags.
4. **"Refetch" is the wrong word.** Published statistics are immutable; we COLLECT MORE cells over time. The verb is **collect**.
5. **Inventory is first-class and inline.** Folded into the indicator JSON, not a sidecar, not a global underscored file. The user's repeated phrase: "no ceremonies, no extras."
6. **All or none with explicit gaps.** Don't ship schema-for-future + real-data-for-favourites. Auto-generate structural fields for ALL indicators; mark methodology gaps explicitly; surface stubs LOUDLY in the dashboard.
7. **Existing admin "Inventory" is election-scoped.** Don't rename. Extend with a sibling `/api/inventory/indicators` endpoint and an Indicator inventory panel in the existing admin shell.
8. **Indian publisher vocabularies don't normalise cleanly.** `as on 31.03.2025`, `Census 2011`, `FY 2024-25`, `Q3 FY25` — any centralised canonicaliser will reach for an LLM; LLM-in-build-step is a non-deterministic dependency we will regret. **The adapter owns its vocabulary; the planner round-trips labels opaquely; the citizen reads them as-is.**
9. **Citizen is a real consumer of `pending_periods[].label`.** Therefore the adapter MUST write citizen-readable labels — "FY 2024-25" passes; "Q1FY25" fails; "2024-04-01T00:00:00Z" fails. Documentation rule, not validator rule.
10. **Strangler-fig over big-bang for the three-way intersection.** Phase 1 ships intent (`series_spec`); phase 2 lets adapters opt into `source_capability`. Same `{key, label, frequency}` shape both sides; emit-layer intersection is one set operation; future opt-in is additive.

---

## §2. Working contract (locked rules — do NOT relitigate)

These are user-locked. If you find yourself wanting to change one, STOP and ask. Do not silently relax.

1. **Fetch-once-freeze at the collect/planner layer.** `Fetcher.fetch()` remains a no-cache HTTP primitive per ADR-0003; the collect layer simply must not call it for already-collected indicator-periods. Raw bytes land in `.runtime/raw/<source>/...` (throwaway debug per ADR-0003). The published contract is the folded indicator JSON under `datasets/`, not `.runtime/`.
2. **`rm` is the only force-recollect mechanism.** No flags, no env vars, no config keys. To force the collect layer to read a URL again: `Remove-Item -LiteralPath ".runtime/raw/<source>/<file>"`; re-run the per-source ingest CLI. Document this in a 5-line how-to.
3. **CLI vocabulary: collect / emit.** Per-source `ingest-*` typer commands keep their names this PR. (Renaming deferred — §13.)
4. **Folded JSON is the collection contract.** No parallel state file, no `.runtime/state.json`, no SQLite registry. The `collection_inventory` block inside each indicator JSON is a **derived view** of `(series_spec) + (rows[] on disk) + (sources[] provenance)`. It does not own state; it reflects it. `.runtime/raw/` is only the local replay / force-recollect affordance.
5. **Folded model.** ONE file per indicator at `datasets/indicators/in/<topic>/<id>.json` holds the existing `indicator + rows[] + license + coverage + sources` contract plus `methodology + collection_inventory + series_spec + divergence`. **NO sidecars.** No `.data-card.json`, no `.notes.json`, no `.meta.json`. The existing `.notes.json` sidecars (10 files) are merged losslessly into typed inline fields and deleted.
6. **All 106 indicators migrate together, via expand → migrate → contract.** Structural fields are auto-generated where safe (`expected_geographies` from a default-or-override table; `expected_periods` from authored/source-backed intent or explicitly marked observed-row seeding; `collection_inventory` derived). Methodology fields are hand-authored where team has knowledge; stub status is explicit elsewhere. Dashboard flags stubs loudly. No silent two-tier.
7. **No hash checks, no byte-compare write-skipping.** Fix non-determinism at source (commit 1).
8. **`fetched_at` keeps its name.** Glossary clarifies meaning. No mass rename.
9. **Planner reads only three fields per indicator.** `collection_inventory.frozen`, `collection_inventory.refetch_requested`, `collection_inventory.pending_periods`. Nothing else. `last_collected_at` is informational; `status` is derived on emit; structured `unavailable_periods` is used by derivation but ignored by the planner.
10. **No normaliser anywhere in the period-label path.** Adapter writes period labels in publisher vocabulary; planner stores, displays, and passes pending tokens back verbatim; adapter recognises its own label/key on the return trip. No LLM. No canonical-form transformer. No shared regex parser. Structured period sets are allowed only as adapter-authored shorthand for clearly iterable source vocabularies.

---

## §3. Goals and non-goals

### §3.1 Goals (this PR delivers all of these)

1. Re-running an ingest with no upstream changes leaves `git status` clean. (Original bug, fixed structurally — commit 1+2.)
2. Every indicator file carries inline `methodology`, `series_spec`, and `collection_inventory` blocks. All 106. No silent tiers. Schema v2.0 enforces.
3. The 10 existing `.notes.json` sidecars are folded losslessly into typed inline methodology fields and deleted.
4. Citizens see "what data we have, what we don't, why we don't, where it came from" on every per-indicator page and on a global `/data-completeness` route.
5. Admin gets an Indicator inventory panel backed by `/api/inventory/indicators`, listing indicators with status, frozen/re-collect chips, pending periods, scope basis, and methodology status.
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

### §3.3 Critical amendments and solution guidelines (authoritative)

This section is the execution correction produced after the critical Gregor / Fowler / Hans / Max / Jony / Citizen review. It does not reopen the locked intent in §2. It fixes the places where the earlier draft would break the live indicator contract, hide schema drift, or turn period labels into a backdoor normaliser.

Where this section conflicts with older wording in §4-§11, **this section wins**.

#### A. Preserve the live indicator artifact shape

The folded model extends the live v1.5 indicator artifact; it does not replace it.

- Keep required top-level fields from `indicator.schema.json` v1.5: `$schema`, `$schema_version`, `sources`, `license`, `coverage`, `indicator`, `rows`.
- Keep the stable id under `indicator.id`; do not add a second root-level id field.
- Do **not** replace `rows[]` with a generic `data` block.
- Add folded sections alongside the existing contract: `methodology`, `series_spec`, `collection_inventory`, and `divergence: null`.
- Existing governance/honesty fields remain authoritative on `indicator`: `comparability`, `attribution_geography`, `funding_split`, `implementing_authority`, `methodology_vintage`, `series_breaks`, `revision_tier_by_period`, `excludes`, `renderer_rules`, `denominator`, and `facet_labels`.
- `methodology` is an editorial wrapper, not a competing honesty schema. If it mirrors breaks, it must use the current `series_breaks[]` semantics (`at_time`, `kind`, `note`) or render from `indicator.series_breaks[]` directly.

#### B. Use expand -> migrate -> contract

Do not add a temporary per-version validator gate. The current backend and frontend validators enforce `$schema_version == x-version`; weakening that rule hides exactly the schema drift this PR is supposed to prevent.

1. **Expand**: bump `indicator.schema.json` `1.5 -> 1.6`. Add folded fields as optional, add `rows[].period_label`, add structured `collection_inventory.unavailable_periods[]`, add `universes.schema.json`, and add `datasets/reference/in/universes.json`. Mechanically bump existing indicator `$schema_version` values to `1.6` so Tier B stays green.
2. **Migrate**: run the migration script across all indicators once. It adds folded content, writes `rows[].period_label`, merges `.notes.json` sidecars inline, deletes sidecars, derives initial `collection_inventory`, and leaves validation green under v1.6.
3. **Contract**: bump `indicator.schema.json` `1.6 -> 2.0`. Make folded sections required, bump all indicators to `2.0`, delete `indicator-notes.schema.json`, and remove all sidecar readers/tests.

#### C. Period model: two explicit tracks plus derived observed state

The user-requested period solution is now locked as a **two-track expected-period model** plus derived inventory state:

1. `series_spec.expected_periods`: the materialized obligation list the indicator intends to track.
2. `series_spec.expected_periods_inference`: the explanation of how that list was obtained. This is where we record whether periods were hand-authored, sourced from a publisher catalogue, seeded from observed rows, or generated from a clearly iterable source-owned series.
3. `collection_inventory.observed_periods`: derived from `rows[]`; never hand-edited.

The public UI should not use the word "inferred". It should say "Planned coverage", "Collected", "Not collected yet", and "Not published by source".

Period token shape:

```jsonc
{
  "key": "2024-04",
  "label": "FY 2024-25",
  "frequency": "annual_fy"
}
```

- `key` is a stable equality token. For v1.5-compatible rows it normally equals `rows[].time`. It is not citizen-facing text.
- `label` is the publisher/adaptor-owned citizen label. It is displayed verbatim and never parsed.
- `frequency` is the fixed enum: `annual_fy`, `annual_cy`, `quarterly_fy`, `quarterly_cy`, `monthly`, `weekly`, `daily`, `decennial`, `ad_hoc`.
- `rows[].time` remains the sortable machine key used by existing renderers.
- `rows[].period_label` is added by v1.6. It carries the same citizen label used by period tokens. For legacy rows, the one-shot migration script may derive it from `time + time_grain`, but that helper stays private to the migration script and must not become a reusable normaliser.

`expected_periods_inference` shape:

```jsonc
{
  "basis": "source_listing",
  "confidence": "clear",
  "series": {
    "mode": "structured",
    "kind": "integer_range",
    "role": "fiscal_year_start",
    "start": 2016,
    "end": 2026,
    "step": 1,
    "key_template": "{year}-04",
    "label_template": "FY {year}-{yy_next}"
  },
  "note": "ICED publishes this annual FY series in the state-wise deep-dive table."
}
```

Allowed `basis` values:

- `authored_from_publisher_catalogue` - the publisher lists the expected periods.
- `authored_from_source_schedule` - the source has a known release cadence or table structure.
- `seeded_from_observed_rows` - migration seeded expected periods from rows already on disk; this is scope-unverified and must be loud in `/data-completeness`.
- `not_inferable` - no widening beyond observed periods is justified.

Allowed structured `series` modes:

- `explicit` - materialized list of period tokens; use for irregular labels and ad hoc periods.
- `structured.integer_range` - clear year-like range, e.g. FY 2016-17 through FY 2025-26.
- `structured.integer_list` - clear non-contiguous years, e.g. Census rounds `[2001, 2011]`.
- `structured.string_list` - clear publisher labels that are iterable only as strings.
- `structured.month_list` / `structured.date_list` - use only when labels and row keys are source-owned and exact.

Structured series may expose interior gaps in a known publisher sequence. They must not invent future obligations just because another year/month might exist. Future/current periods need publisher evidence, a source listing, or explicit adapter knowledge.

#### D. Inventory derivation semantics

`derive_collection_inventory(indicator, universes)` is pure and repo-deterministic. It reads committed indicator JSON and reference universes only. It must not read `.runtime/raw/` while deriving committed inventory.

Collected cells:

- Base key: `(rows[].entity_id, rows[].period_label)` where `value !== null`.
- Zero is collected. `null` is not collected.
- For faceted rows, v2.0 counts the geography/period as collected when at least one non-null row exists for that pair. Full facet-completeness is adapter-specific and deferred.

Algorithm:

1. Resolve `series_spec.expected_geographies` inline or via `universes.json`.
2. Expand `series_spec.expected_periods` to materialized period tokens.
3. Build expected cells = expected geographies x expected period tokens.
4. Build collected cells from `rows[].entity_id + rows[].period_label`.
5. Build unavailable cells from structured `collection_inventory.unavailable_periods`.
6. Pending cells = expected - collected - unavailable.
7. Emit one `pending_periods[]` token when any geography remains pending for that period.
8. Emit `observed_periods[]` from rows, sorted by the period token key / sequence supplied by the adapter or migration.
9. Preserve `frozen`, `refetch_requested`, and structured `unavailable_periods` from the existing file; default booleans to `false` and arrays to `[]`.
10. Derive `last_collected_at` as `max(sources[].fetched_at)`, or `null` when `sources` is empty.
11. Derive `status`: `empty` when no collected cells, `partial` when any pending period remains, otherwise `complete`.

Structured unavailable entries:

```jsonc
{
  "period": { "key": "2011", "label": "Census 2011", "frequency": "decennial" },
  "geographies": ["U09"],
  "reason": "Ladakh did not separately exist in Census 2011 tables."
}
```

- `geographies` omitted means the whole expected period is unavailable.
- `reason` is citizen-visible and mandatory.
- Derivation subtracts these cells before computing pending periods.

#### E. Scope and methodology status must be explicit

Completeness cannot mean "we have whatever rows happened to be on disk".

- Add `series_spec.expected_periods_inference.basis` as above.
- Add `methodology.documentation_status`: `stub`, `partial`, `authored`.
- `/data-completeness` must distinguish `seeded_from_observed_rows` from publisher-verified scope.
- Only publisher/source-backed scope may be called fully collected without a caveat. Observed-row-only scope renders as `scope unverified` / `draft coverage` in admin and as a visible stub on public completeness views.

#### F. Fold sidecars losslessly

The 10 `.notes.json` sidecars contain typed editorial fields. They must not be flattened into `methodology.notes[]`.

Required mapping:

- `related[]` -> `methodology.related_indicators[]`
- `editor_note_md` -> `methodology.editor_note_md`
- `policy_context[]` -> `methodology.policy_context[]`
- `chart_defaults` -> `methodology.chart_defaults`

Delete `indicator-notes.schema.json` only after the migration and page generator prove these fields are preserved inline.

#### G. ADR-0003 resolution

This PR changes behavior around collection planning, not `Fetcher.fetch()` itself.

- Core HTTP still has no cache; every `Fetcher.fetch()` call hits the network.
- The collect/planner layer does not call `Fetcher.fetch()` for already-collected indicator-periods.
- `.runtime/raw/` remains gitignored, schema-less, and non-production. It may guide local replay or force-recollect, but the committed contract is the folded indicator JSON.
- ADR-0003 and `docs/architecture/data-flow.md` must be amended in the same commit that implements this behavior.

#### H. Static index for `/data-completeness`

The public frontend cannot list `datasets/indicators/in/` at runtime. Add a first-class, schema-validated static index under `datasets/reference/in/`, e.g. `indicator-inventory.json`.

The index includes every indicator path plus: id, title, topic/catalogue status, publisher, inventory status, expected period count, expected geography count, expected cell count, collected cell count, pending period count, unavailable cell count, methodology status, scope basis, `frozen`, `refetch_requested`, and `last_collected_at`.

This is not the rejected global `_inventory.json`: it is a public navigation/completeness index under `datasets/reference/in/`, with a schema and `sources: []` if generated from committed artifacts.

#### I. UI and copy rules

Public labels:

- `complete` -> `Collected for all planned states and periods`
- `partial` -> `Partly collected`
- `empty` -> `No data collected yet`
- `pending` -> `Not collected yet`
- `unavailable` -> `Not published by source`
- `frozen` -> `Collection paused`
- `refetch_requested` -> `Re-collect requested` in admin only; avoid public display unless there is an explanatory operator context.
- `last_collected_at` / `sources[].fetched_at` -> `Collected from source on` or `Latest source read`, never `Last updated`.

Citizen helper copy for source dates:

> Collected from source on this date. This is when yen-gov read the listed URL, not when the publisher changed the data.

`AboutThisData` has two modes:

- `compact` for cards/lists: one trust strip (`Partly collected · 3 pending periods · 4 sources`).
- `full` for chart/detail surfaces: methodology, scope, collected/pending/unavailable, caveats, breaks, notes, and sources.

Do not use toggle-looking controls for read-only `frozen` or `refetch_requested`; use status chips until admin write-actions land.

#### J. Docs and tests move with the changes

Do not keep a final docs-only commit. Docs travel with the contract or behavior they explain.

Test amendments:

- Schema: v1.6 accepts optional folded fields; v2.0 requires them.
- Periods: explicit period list validates; structured integer range/list validates; irregular labels require explicit mode; no helper parses `FY 2024-25` into an ISO interval.
- Derivation: `observed_periods` comes from rows; zero is collected; `null` is not; structured unavailable periods subtract correctly; operator flags are preserved; universe `$ref` resolves; output is deterministic.
- Migration: idempotent second run; no `.notes.json` remains; sidecar fields preserved inline; all paths emitted by tooling are POSIX-relative.
- Integration: `python -m yen_gov coverage` twice leaves no diff after inventory refresh is wired.
- Frontend/admin: `/data-completeness`, one representative indicator page, one state topic page, and the admin indicator panel render on desktop and mobile with no console errors, no new 404s, and no horizontal overflow on public routes.

Windows-safe execution notes:

```powershell
$env:PYTHONPATH = "backend"
python tools/migrate_indicators_v15_to_v20.py --check
python tools/migrate_indicators_v15_to_v20.py --write
python -m yen_gov validate
python -m pytest -q
python -m yen_gov coverage
python -m yen_gov coverage
git add --pathspec-from-file .runtime/folded-indicator-migration-paths.txt
git diff --cached --name-only
```

Avoid brace expansion, broad globs, `git add .`, `git add -A`, `Set-Content` for UTF-8 JSON/Markdown, and inline multi-line Python.

---

## §4. Commit slate

Two-hat discipline (Tidy First / Kent Beck): structural commits never mix with behavioural commits. Each commit independently shippable, testable, reviewable.

| # | Hat | Title | One-liner |
|---|---|---|---|
| 1 | **behavioural** | Remove `datetime.now()` from derived outputs | Structural determinism fix. Kills derived-output timestamp churn without byte-compare helpers. |
| 2 | **behavioural** | Composer per-URL dedup | `_union_sources` dedups by URL alone; defensive cleanup of historical accumulated duplicates. |
| 3 | **structural** | Expand indicator schema to v1.6 | Add optional folded fields, `rows[].period_label`, structured unavailable periods, universes schema/data, and mechanically bump indicators to v1.6. |
| 4 | **structural** | Add inventory derivation module | Pure Python module computes `collection_inventory` from committed `indicator + rows[] + series_spec`; unit-tested. No CLI wire-up yet. |
| 5 | **structural** | Add migration tooling and overlays | Idempotent `tools/migrate_indicators_v15_to_v20.py`, typed overlays/fixtures, sidecar-losslessness tests. |
| 6 | **structural/data** | Migrate all indicators to folded v1.6 | Add folded fields to all indicators, write `rows[].period_label`, merge/delete `.notes.json` sidecars, derive initial inventory. |
| 7 | **structural/contract** | Contract indicator schema to v2.0 | Make folded fields required, bump all indicators to v2.0, delete `indicator-notes.schema.json`, remove sidecar readers/hooks. |
| 8 | **behavioural** | Wire inventory refresh and admin endpoint | Wire derivation into the appropriate backend emit/coverage entry point; add `/api/inventory/indicators`. |
| 9 | **structural** | Frontend folded types and static index | Extend existing indicator types/loaders, add `indicator-inventory.json` contract, no UI wire-up yet. |
| 10 | **behavioural** | Render data completeness surfaces | Add `AboutThisData`, `/data-completeness`, admin indicator panel, copy updates, and browser verification. |

Commits 1+2 ship the original bug fix. Commits 3-7 deliver folded-indicator + inventory contracts and migration safely via expand -> migrate -> contract. Commits 8-10 wire backend/admin/frontend behavior. Docs move with the commits they explain; only memory/index cleanup may remain at the end.

**Branch name:** `feature/folded-indicator-inventory`

---

## §5. Per-commit deep dive

**Read this section through §3.3.** The original draft below was amended after critical review. Any older wording that conflicts with the live artifact shape, structured period model, strict validator path, or amended commit slate is superseded by §3.3 and §4.

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

### §5.3 Commit 3 — Expand schema v1.6 + universes.json

**Files modified:**

#### [datasets/schemas/indicator.schema.json](datasets/schemas/indicator.schema.json) — v1.5 -> v1.6

**Expand rationale:** add the folded fields as optional first so backend and frontend validators stay strict and green. Commit 7 contracts v1.6 -> v2.0 after all indicators have migrated.

Add to `x-changelog`:
```json
{
  "version": "1.6",
  "date": "2026-05-17",
  "description": "Expand phase for the folded indicator model. Adds optional methodology, series_spec, collection_inventory, divergence, rows[].period_label, and structured unavailable periods. Existing v1.5 long-form fields remain required. Contract to required folded fields lands in v2.0 after migration."
}
```

New optional top-level keys in v1.6 (required only in v2.0):
- `methodology` (object) — see §3.3.F and §6.1.
- `series_spec` (object) — see §3.3.C. Contains `expected_geographies`, materialized `expected_periods`, and `expected_periods_inference`.
- `collection_inventory` (object) — see §3.3.D. Includes `observed_periods`, `pending_periods`, structured `unavailable_periods`, status/flags, and `last_collected_at`.
- `divergence` — reserved nullable field.

New optional row key in v1.6:
- `rows[].period_label` — adapter-owned citizen label matching period tokens. Existing `rows[].time` remains the machine sort/join key.

Existing top-level keys (`license`, `coverage`, `indicator`, `rows`, `sources`, `$schema`, `$schema_version`, etc.) retained unchanged. `coverage.*` keeps its existing role as editorial-prose siblings to the new structured `expected_*` fields.

#### [datasets/schemas/indicator-notes.schema.json](datasets/schemas/indicator-notes.schema.json) — UNCHANGED in this commit

Deletion deferred to commit 7 (after sidecar content is folded into parents and v2.0 contracts the schema).

#### [datasets/schemas/universes.schema.json](datasets/schemas/universes.schema.json) — NEW (`x-version: "1.0"`)

Validates the lookup table for "named sets of geo codes."

#### [datasets/reference/in/universes.json](datasets/reference/in/universes.json) — NEW

Named geo-code sets, `$ref`-able from `series_spec.expected_geographies`. Inline arrays also allowed; this file is convenience only (user direction: keep, no deletion ceremony). Initial entries:
- `all_states_and_uts` (36 geo codes)
- `states_only_no_ut` (28)
- `union_only` (`["IN"]`)
- `pre_2014_states_only` (29 — pre-bifurcation Andhra Pradesh).

Add more entries opportunistically in commit 6 if migration reveals additional natural sets.

**No validator switch.** Mechanically bump existing indicators to `$schema_version: "1.6"` in this commit after the optional fields land. Keep the existing strict `$schema_version == x-version` invariant in both backend and frontend tests.

**Tests:**
- [backend/tests/test_indicator_schema.py](backend/tests/test_indicator_schema.py) (extend or new) — Tier A meta-validation of v2.0 schema.
- [backend/tests/test_universes_schema.py](backend/tests/test_universes_schema.py) (new) — Tier A + Tier B for universes.
- [backend/tests/test_validate.py](backend/tests/test_validate.py) (extend) — assert strict version equality still holds; v1.6 old-shape indicators validate; v2.0 contraction is tested in commit 7.

### §5.4 Commit 4 — Inventory derivation module

**New module:** `backend/yen_gov/inventory/`

```
backend/yen_gov/inventory/
  __init__.py
  derive.py             # derive_collection_inventory(indicator_dict, universes) -> dict
  detect_cells.py       # walk indicator.rows, return collected (entity_id, period_label) cells
  diff_expected.py      # given series_spec + collected cells, compute pending_periods[]
  overlay.py            # load methodology overlay JSON (hand-authored caveats / breaks / notes)
```

**`derive.py` algorithm (pure function, deterministic — same input → same output bytes):**

1. Read the existing `indicator + rows[]` contract. Extract collected cells from rows where `value !== null` as `(entity_id, period_label)`; zero counts as collected.
2. Read `series_spec.expected_geographies` (inline array OR resolve `$ref` against universes.json) and materialized `series_spec.expected_periods` period tokens.
3. Compute `pending_periods` = expected geographies × expected periods minus collected cells minus structured `unavailable_periods` entries. Group by period: a period is "pending" if ANY expected geography remains missing. Emit one period token per pending period.
4. `status` derived: `"complete"` if `pending_periods == []` AND `unavailable_periods == []`-or-explained; `"partial"` if any pending; `"empty"` if zero collected.
5. `observed_periods` derived from rows. `last_collected_at` derived as max of `sources[].fetched_at`; if `sources` is empty, use `null`.
6. `frozen` and `refetch_requested` preserved from existing values on the indicator file. (Operator-set; never derived. Default both `false`.)
7. `unavailable_periods` preserved from existing values (operator-set; never derived). Default `[]`.

**Tests:** [backend/tests/test_inventory_derive.py](backend/tests/test_inventory_derive.py) (new):
- `test_derive_against_fixture_complete_series` — all cells present → `status: "complete"`, `pending_periods == []`.
- `test_derive_partial_series_lists_pending` — 10 of 36 states present for one period → that period appears in `pending_periods` with correct `frequency`.
- `test_derive_is_deterministic` — twice on same input → byte-identical output.
- `test_derive_preserves_operator_flags` — input has `frozen: true, refetch_requested: true` → output preserves both.
- `test_derive_status_states` — exercise complete / partial / empty.

### §5.5 Commit 8 — Wire derivation into backend refresh + admin endpoint

**Backend:**
- [backend/yen_gov/cli.py](backend/yen_gov/cli.py) / [backend/yen_gov/coverage.py](backend/yen_gov/coverage.py) — wire the pure derivation into the appropriate backend refresh entry point. After existing report write, walk all indicator files; for each, call `inventory.derive.derive_collection_inventory(...)`; write the updated `collection_inventory` block back deterministically.
- [backend/yen_gov/admin/inventory.py](backend/yen_gov/admin/inventory.py) — ADD `/api/inventory/indicators` GET endpoint. Returns JSON list of `{id, title, topic, status, frozen, refetch_requested, pending_period_count, scope_basis, methodology_status, last_collected_at}` for all indicators. Existing election inventory endpoints unchanged.

**Determinism guarantee:** with commit 1 + commit 4 in place, re-runs produce byte-identical `collection_inventory` blocks -> no `git status` churn.

**Test:** [backend/tests/test_coverage_emits_inventory.py](backend/tests/test_coverage_emits_inventory.py) (new) — fixture tree with 3 indicators (already at v2.0) -> run refresh/coverage -> assert each indicator file's `collection_inventory` block matches expected -> re-run -> assert byte-identical.

### §5.6 Commit 6 — Migrate all indicators to folded v1.6 + delete sidecars

**Volume commit. Single PR-review event.**

**Steps:**
1. Hand-author schema-validated methodology overlay input keyed by `indicator.id`. Sparse: ~10-20 indicators where team has domain knowledge (RBI Handbook, CAG state accounts, ECI parsing notes, ICED data-quality caveats). If the overlay is one-shot migration input, keep it under `tools/`; if it remains reference data, place it under `datasets/reference/` or `config/` with `sources: []`.
2. Hand-author schema-validated expected-geographies overrides for indicators whose geographies are not the default implied by `indicator.entity_kind`. Include country-only, state-only, all-states-plus-India, UT-excluding, CEA 35-entity, pre-2014, and J&K/Ladakh exceptions as needed.
3. Run the idempotent migration script (`tools/migrate_indicators_v15_to_v20.py`, default `--check`, mutating `--write`): for each indicator file, add `methodology`, `series_spec`, `collection_inventory`, `divergence`, and `rows[].period_label`; keep `$schema_version` at `"1.6"` in this commit.
4. For each of the 10 indicators with a sibling `.notes.json` sidecar: read sidecar, merge `related[]`, `editor_note_md`, `policy_context[]`, and `chart_defaults` into typed inline fields, then delete the sidecar.
5. Keep `datasets/schemas/indicator-notes.schema.json` until commit 7 contraction deletes the schema and any sidecar hooks.
6. Contract to v2.0 happens in commit 7, not here.
7. Run inventory derivation to populate `collection_inventory` blocks. Verify a second run is deterministic and produces no diff.
8. Eyeball dashboard counts: how many indicators are `methodology.documentation_status: "stub"` and how many have `expected_periods_inference.basis: "seeded_from_observed_rows"`? Expected: many. Acceptable only because they surface loudly on `/data-completeness`.
9. Use the migration script's POSIX pathspec file for staging; do not rely on shell glob or brace expansion in PowerShell.

**Tests:**
- [backend/tests/test_datasets_integrity.py](backend/tests/test_datasets_integrity.py) (extend) — every indicator file validates; every `indicator.id` matches its directory; no `.notes.json` files exist under `datasets/indicators/`; sidecar fields are preserved inline; all emitted paths are POSIX-relative.

### §5.7 Commit 9 — Frontend loader + types + static index

**Files modified/created:**
- `frontend/src/lib/indicator.ts` (extend or new) — types matching v2.0 schema:
  ```ts
  export type PeriodFrequency = "annual_fy" | "annual_cy" | "quarterly_fy" | "quarterly_cy"
    | "monthly" | "weekly" | "daily" | "decennial" | "ad_hoc";
  export interface PeriodToken { key: string; label: string; frequency: PeriodFrequency; }
  export interface SeriesSpec {
    description: string;
    expected_geographies: string[];        // inline OR resolved $ref
    expected_periods: PeriodToken[];
    expected_periods_inference: {
      basis: "authored_from_publisher_catalogue" | "authored_from_source_schedule" | "seeded_from_observed_rows" | "not_inferable";
      confidence: "clear" | "partial" | "none";
      series: unknown | null;
      note?: string;
    };
  }
  export type InventoryStatus = "complete" | "partial" | "empty";
  export interface CollectionInventory {
    status: InventoryStatus;
    frozen: boolean;
    last_collected_at: string | null;
    refetch_requested: boolean;
    observed_periods: PeriodToken[];
    pending_periods: PeriodToken[];
    unavailable_periods: { period: PeriodToken; geographies?: string[]; reason: string }[];
  }
  export interface MethodologyBreak { at: string; note: string; }
  export interface IndicatorMethodology {
    definition: string;
    publisher: string;
    publisher_methodology_url: string | null;
    methodology_breaks: MethodologyBreak[];
    known_caveats: string[];
    notes: string[];                         // free-form methodology notes; sidecar fields keep typed homes below
    documentation_status: "stub" | "partial" | "authored";
    related_indicators?: string[];
    editor_note_md?: string;
    policy_context?: string[];
    chart_defaults?: Record<string, unknown>;
  }
  export interface Indicator {
    $schema: string;
    $schema_version: string;
    indicator: IndicatorMeta;                 // existing v1.5 metadata shape, extended rather than replaced
    rows: IndicatorRow[];                     // existing long-form rows, with optional period_label
    license: IndicatorLicense;
    series_spec: SeriesSpec;
    collection_inventory: CollectionInventory;
    methodology: IndicatorMethodology;
    coverage: { spatial: string; temporal: string; admin_level?: string | null };
    sources: { url: string; fetched_at: string; name?: string; authority?: string }[];
    divergence: null;
  }
  ```
- Loader function `fetchIndicator(path)` — fetches the single JSON; no separate sidecar fetch (folded model). Extend existing `frontend/src/lib/indicators.ts` types rather than creating a competing shape if that remains the local pattern.
- Static index loader — fetches `datasets/reference/in/indicator-inventory.json` via `/data/reference/in/indicator-inventory.json` for `/data-completeness`.

**Tests:**
- [frontend/src/contracts/datasets-conform.test.ts](frontend/src/contracts/datasets-conform.test.ts) (extend) — validate all v2.0 indicator files and `reference/in/indicator-inventory.json` against schemas using ajv.
- [frontend/src/lib/indicator.test.ts](frontend/src/lib/indicator.test.ts) (extend or new) — loader unit tests: parses sample, asserts folded shape preserves `indicator + rows[]`.
- [frontend/src/lib/indicatorInventory.test.ts](frontend/src/lib/indicatorInventory.test.ts) (new) — static index loader parses all rows and has no directory-listing dependency.

**No UI wire-up in this commit.** Pure structural.

### §5.8 Commit 10 — Frontend rendering + admin panel

**Public frontend:**
- `frontend/src/lib/AboutThisData.svelte` (new) — renders methodology + inventory:
  - **What this measures** — from `methodology.definition`.
  - **Source** — publisher + link to `publisher_methodology_url`.
  - **Coverage** — "X of Y expected cells collected" + per-state status grid.
  - **Not collected yet** — list `pending_periods[].label`. Citizen reads labels as-is; no normalisation.
  - **Not published by source** — list structured `unavailable_periods[]` as `period.label` plus reason and affected geographies where present.
  - **Known caveats** — bullet list (hide section if empty).
  - **Methodology breaks** — bullet list (hide if empty).
  - **Notes** — bullet list from `methodology.notes[]`; render `editor_note_md`, `policy_context[]`, `related_indicators[]`, and `chart_defaults` through their typed homes where relevant.
  - **Sources** — render `sources[]` URLs + "Collected from source on" dates derived from `fetched_at`.
- `frontend/src/routes/DataCompleteness.svelte` (new route `/data-completeness`) — loads the static indicator inventory index, not a directory listing. Columns: id/title, topic, status, coverage cells, pending periods, collection state, methodology status, scope basis, latest source read, catalogue reachability. Sortable. Row total at top: collected / partly collected / not collected, plus methodology-authored / stub counts.
- Existing indicator components (`IndicatorCard.svelte`, `StateTopic.svelte`, `TopicLanding.svelte`) — insert `<AboutThisData ... />` below the chart.
- Routes registry — add `/data-completeness`; add `url.dataCompleteness()` and a rail/about link so the route is discoverable.

**Admin panel:**
- `admin/src/routes/Indicators.svelte` (new) — list view backed by `/api/inventory/indicators`. Columns: id/title, topic, status, pending periods, methodology status, frozen chip, re-collect requested chip, last collected. Sort + filter. This is a sibling **panel** in the existing admin shell, not a new URL router.
- `admin/src/lib/api.ts` — add `indicatorInventory()` / equivalent typed client.
- Existing `Inventory.svelte` (elections) remains the election inventory; nav label may become "Election inventory" with a sibling "Indicator inventory" panel.
- `admin/src/routes/Pipeline.svelte`, `EciRecon.svelte` — cosmetic copy fixes: stop leaking `.runtime/` paths in user-visible strings (per CLAUDE.md §10 — `.runtime/` is internal throwaway, not a citizen / operator surface).

**Tests:**
- [frontend/src/lib/AboutThisData.test.ts](frontend/src/lib/AboutThisData.test.ts) (new) — vitest unit: renders with sample, hides empty sections, displays pending labels verbatim (no transformation).
- [frontend/e2e/golden-path.spec.ts](frontend/e2e/golden-path.spec.ts) (extend) — assert "About this data" renders on one representative indicator route.
- [frontend/e2e/data-completeness.spec.ts](frontend/e2e/data-completeness.spec.ts) (new) — Playwright: route loads from the static index, no console error, table has all indicators, at least one stub/scope-unverified row visible.
- [admin/e2e/indicators-panel.spec.ts](admin/e2e/indicators-panel.spec.ts) or extension of existing panel e2e — Playwright: panel loads in the existing shell, table renders, no console error.

**UI verification per CLAUDE.md §13 (MANDATORY):** before merging this commit:
1. Start frontend (`bun run dev` in `frontend/`, port 5173). Start admin (`bun run dev` in `admin/`, port 5174).
2. `open_browser_page` to `http://localhost:5173/` -> one representative indicator route -> `/data-completeness`. `read_page` each; confirm no `[error]` console events; confirm "About this data" section renders; confirm pending period labels display verbatim.
3. `open_browser_page` to `http://localhost:5174/` -> Indicators panel. `read_page`; confirm panel renders; confirm no new 404s.
4. `screenshot_page` one indicator page showing "About this data."
5. Record in commit message: routes verified.

### §5.9 Documentation + memory + ADR ownership

Required by CLAUDE.md §4 ("A code commit without its rationale doc is incomplete"). These docs move with the commits that change the corresponding contract or behavior; do not save them for a final docs-only commit.

**Files created or rewritten:**

1. **`docs/concepts/folded-indicator.md` (new)** — canonical concept doc:
  - What the folded model is (one file: existing `indicator + rows[] + license + coverage + sources` plus `methodology + series_spec + collection_inventory + divergence`).
   - Why folded (rejected sidecar models; lifecycles are one).
   - Schema link.
   - Glossary (paste from §7 of this handover).
   - "As-published fidelity, not correctness" (Hans).
   - Forward-looking: divergence (Max, deferred); adapter `source_capability` (deferred phase 2).

2. **`docs/concepts/collection-inventory.md` (new)** — companion:
  - Inventory fields, what each means, who writes each (operator / derived / adapter).
   - Planner reads only `frozen` + `refetch_requested` + `pending_periods`.
  - The `{key, label, frequency}` opaque-token contract (no normaliser).
  - `expected_periods` vs `expected_periods_inference` vs derived `observed_periods`.
   - Adapter MUST write citizen-readable labels (the documentation rule from §1.4 lesson #9).
   - `rm` is the only force-recollect; link to the how-to.

3. **`docs/concepts/data-quality.md` (new)** — Hans-authored stance:
   - We re-publish; we don't correct, smooth, impute, estimate.
   - Empty cells stay empty.
   - Gaps are loud, not hidden.

4. **`docs/architecture/decisions/0003-no-fetch-cache.md`** — amend with a "Clarifications 2026-05-17" section:
   - No-cache stance stands.
  - `.runtime/raw/` is throwaway debug, not a published inventory record.
  - Core fetcher still has no cache; collect/planner layer simply does not call it for already-collected indicator-periods.
  - Folded indicator model lives at a higher layer and clarifies that the committed indicator JSON is the contract surface.

5. **`docs/how-to/force-recollect.md` (new, ~30 lines, only if still useful after collect/planner wording)** — operator runbook for explicit re-collection.

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
// Existing v1.5 fields remain required: $schema, $schema_version, sources, license,
// coverage, indicator, rows. Below shows only the folded sections added by v1.6
// and required by v2.0. `indicator.id` remains the stable id; `rows[]` remains
// the long-form observation surface.

"series_spec": {
  "type": "object",
  "additionalProperties": false,
  "required": ["description", "expected_geographies", "expected_periods", "expected_periods_inference"],
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
        "required": ["key", "label", "frequency"],
        "properties": {
          "key": {
            "type": "string",
            "minLength": 1,
            "description": "Stable equality token. Normally equals rows[].time. Not citizen-facing."
          },
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
    },
    "expected_periods_inference": {
      "type": "object",
      "additionalProperties": false,
      "required": ["basis", "confidence", "series"],
      "properties": {
        "basis": {
          "enum": ["authored_from_publisher_catalogue", "authored_from_source_schedule", "seeded_from_observed_rows", "not_inferable"]
        },
        "confidence": { "enum": ["clear", "partial", "none"] },
        "series": {
          "description": "Optional adapter-authored shorthand for a clearly iterable period set. Null when explicit periods are used or no inference is justified.",
          "oneOf": [
            { "type": "null" },
            {
              "type": "object",
              "additionalProperties": false,
              "required": ["mode", "kind", "role"],
              "properties": {
                "mode": { "enum": ["explicit", "structured"] },
                "kind": { "enum": ["integer_range", "integer_list", "string_list", "month_list", "date_list"] },
                "role": { "type": "string", "minLength": 1 },
                "start": { "oneOf": [{ "type": "integer" }, { "type": "string" }] },
                "end": { "oneOf": [{ "type": "integer" }, { "type": "string" }] },
                "step": { "type": "integer", "minimum": 1 },
                "values": { "type": "array", "items": { "oneOf": [{ "type": "integer" }, { "type": "string" }] } },
                "key_template": { "type": "string" },
                "label_template": { "type": "string" }
              }
            }
          ]
        },
        "note": { "type": "string" }
      }
    }
  }
},

"collection_inventory": {
  "type": "object",
  "additionalProperties": false,
  "required": ["status", "frozen", "last_collected_at", "refetch_requested", "observed_periods", "pending_periods", "unavailable_periods"],
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
      "description": "Derived: expected periods x expected geographies minus collected minus unavailable. Planner reads and passes period tokens back to the adapter verbatim.",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["key", "label", "frequency"],
        "properties": {
          "key": { "type": "string", "minLength": 1 },
          "label": { "type": "string", "minLength": 1 },
          "frequency": { "enum": ["annual_fy", "annual_cy", "quarterly_fy", "quarterly_cy", "monthly", "weekly", "daily", "decennial", "ad_hoc"] }
        }
      }
    },
    "observed_periods": {
      "type": "array",
      "description": "Derived from rows[].time and rows[].period_label. Never hand-edited.",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["key", "label", "frequency"],
        "properties": {
          "key": { "type": "string", "minLength": 1 },
          "label": { "type": "string", "minLength": 1 },
          "frequency": { "enum": ["annual_fy", "annual_cy", "quarterly_fy", "quarterly_cy", "monthly", "weekly", "daily", "decennial", "ad_hoc"] }
        }
      }
    },
    "unavailable_periods": {
      "type": "array",
      "description": "Structured cells or whole periods excluded from pending because the source does not publish them or the cell cannot exist.",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["period", "reason"],
        "properties": {
          "period": {
            "type": "object",
            "additionalProperties": false,
            "required": ["key", "label", "frequency"],
            "properties": {
              "key": { "type": "string", "minLength": 1 },
              "label": { "type": "string", "minLength": 1 },
              "frequency": { "enum": ["annual_fy", "annual_cy", "quarterly_fy", "quarterly_cy", "monthly", "weekly", "daily", "decennial", "ad_hoc"] }
            }
          },
          "geographies": { "type": "array", "items": { "type": "string", "minLength": 1 } },
          "reason": { "type": "string", "minLength": 10 }
        }
      }
    }
  }
},

"methodology": {
  "type": "object",
  "additionalProperties": false,
  "required": ["definition", "publisher", "documentation_status", "methodology_breaks", "known_caveats", "notes"],
  "properties": {
    "definition": { "type": "string", "description": "One-paragraph plain-English definition of what this indicator measures." },
    "publisher": { "type": "string", "description": "Issuing authority. e.g. 'Reserve Bank of India'." },
    "publisher_methodology_url": { "type": ["string", "null"], "format": "uri" },
    "documentation_status": { "enum": ["stub", "partial", "authored"] },
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
      "description": "Free-form methodological notes. Former .notes.json sidecar fields get their own typed homes; do not flatten them all here.",
      "items": { "type": "string", "minLength": 1 }
    },
    "related_indicators": { "type": "array", "items": { "type": "string", "minLength": 1 } },
    "editor_note_md": { "type": "string" },
    "policy_context": { "type": "array", "items": { "type": "string", "minLength": 1 } },
    "chart_defaults": { "type": "object" }
  }
},

"divergence": {
  "description": "Reserved for Max's divergence-band methodology (deferred). Always null in v2.0.",
  "type": "null"
}
```

### §6.2 `universes.schema.json` v1.0 (new)

Validates `datasets/reference/in/universes.json`. The schema file carries standard `$schema`, `$id`, `title`, `description`, `x-version`, and `x-changelog`. The data file carries `$schema`, `$schema_version`, `sources: []` (hand-authored reference data), and a top-level `universes` map; each entry has `description`, `geo_codes[]`, and `expected_count`.

### §6.3 `indicator-notes.schema.json` — deleted in commit 7

After sidecar content is folded losslessly into typed parent fields (`related_indicators`, `editor_note_md`, `policy_context`, `chart_defaults`) and all indicators validate under the contracted v2.0 schema.

---

## §7. Glossary (paste verbatim into `docs/concepts/folded-indicator.md`)

> **Folded indicator.** A single JSON file per indicator at `datasets/indicators/in/<topic>/<id>.json` holding the existing `indicator + rows[] + license + coverage + sources` contract plus `methodology + series_spec + collection_inventory + divergence` inline. No sidecars.
>
> **Series cell.** A single observation, identified by `(entity_id, period_label)`. For "state GSDP, annual FY, 2011-12 to 2024-25" with `all_states_and_uts` geographies, the universe is 36 x 14 = 504 cells.
>
> **`series_spec`.** Declares what the series IS — description, expected geographies, expected periods. The editorial source of truth for what we promise to track.
>
> **`expected_geographies`.** Array of geo codes (ECI state codes, district LGD, or `IN`). Inline or `$ref` into [`universes.json`](../../datasets/reference/in/universes.json).
>
> **`expected_periods`.** Materialized array of `{key, label, frequency}` period tokens. `key` is the equality token, normally matching `rows[].time`; `label` is the publisher's exact vocabulary ("FY 2024-25", "as on 31.03.2025", "Census 2011"); `frequency` is a fixed enum.
>
> **`expected_periods_inference`.** Explains how `expected_periods` was obtained: publisher catalogue, source schedule, observed rows, or not inferable. It may include an adapter-authored structured series (integer range/list, string list, month/date list) when the source vocabulary is clearly iterable. This is admin/schema language; public pages say "Planned coverage" or "Draft coverage", not "inferred".
>
> **`collection_inventory`.** Derived + operator-flagged view of where we stand on this indicator. Fields: `status`, `frozen`, `last_collected_at`, `refetch_requested`, `observed_periods`, `pending_periods`, `unavailable_periods`.
>
> **`status`.** `complete` (zero pending, zero unexplained gaps) | `partial` (some pending) | `empty` (zero collected). Derived on emit.
>
> **`frozen`.** Operator flag. When true, planner skips this indicator entirely on next collect.
>
> **`last_collected_at`.** Derived: `max(sources[].fetched_at)`. Informational only. Planner does not read.
>
> **`refetch_requested`.** Operator triage flag. In this PR it is read-only status, not a second force-recollect mechanism. Public copy should say "Re-collect requested" only in admin/operator contexts.
>
> **`observed_periods`.** Derived array of period tokens actually present in `rows[]`. Never hand-edited.
>
> **`pending_periods`.** Derived array of period tokens for periods the indicator expects but has not yet collected and has not marked unavailable. Planner stores, displays, and passes back verbatim — never parses or normalises.
>
> **`unavailable_periods`.** Structured exclusions with `{period, geographies?, reason}`. Example: `Census 2011` for Ladakh, reason "Ladakh did not separately exist in Census 2011 tables." Citizen-visible; used by derivation to avoid marking impossible cells as pending.
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
> **As-published fidelity, not correctness.** yen-gov preserves publisher values and documents every transformation we perform: parsing tables, mapping geographies, choosing revision vintages, and computing declared rollups. No adjustment, smoothing, imputation, or correction. Errors in the original appear here; we update when the publisher does.
>
> **Adapter ownership of labels.** The adapter is the single authority on its source's period vocabulary. It writes labels in the publisher's own form and recognises them on the return trip. The planner never parses. No normaliser, no LLM, no canonical-form transformer anywhere in the path.

---

## §8. Frontend copy (Hans-authored, paste-ready)

### §8.1 About page (`frontend/src/routes/About.svelte`)

> # About yen-gov
>
> yen-gov republishes Indian governance and statistical data from official and public sources. We preserve publisher values and document every transformation we perform: parsing tables, mapping geographies, choosing revision vintages, and computing declared rollups. We are a re-publisher, not a statistical agency.
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
> - **Sources.** Exact URLs with the date yen-gov read them.
>
> Indicators where we haven't yet documented methodology are flagged visibly. See `/data-completeness` for the full inventory.
>
> ## What we don't do
>
> - We do not adjust, smooth, impute, or correct published values. Publisher errors appear here; we update when the publisher does.
> - We do not estimate. Missing cells are marked **Not collected yet** or **Not published by source** — never filled in.
> - We do not maintain a live API. The site is a static snapshot; we collect periodically and ship a new bundle.
>
> ## Trust, in one sentence
>
> Trust the data exactly as far as you trust the publisher. yen-gov's job is to make their data more accessible without changing what they said.

### §8.2 Disclaimer page (`frontend/src/routes/Disclaimer.svelte`)

> # Disclaimer
>
> yen-gov is a re-publisher of government and statistical data from entities including the Reserve Bank of India, the Election Commission of India, the Comptroller and Auditor General, the Ministry of Statistics and Programme Implementation, and others. We preserve publisher values and document parser, geography, vintage, and rollup transformations.
>
> **Accuracy.** The figures shown here reflect what the listed publishers published at the time we collected them. We do not independently verify, correct, or estimate any figure. Errors in the original publication appear here; we update when the publisher updates.
>
> **Completeness.** Many indicators are partially collected. We mark missing cells as **Not collected yet** (source expected to publish) or **Not published by source** (publisher does not separately report this geography or period). Empty cells are never filled with estimates.
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
3. `backend/tests/test_indicator_schema.py` (new or extend) — Tier A meta-validation for v1.6 expansion and v2.0 contraction; period token/inference shapes validate (commits 3 and 7).
4. `backend/tests/test_universes_schema.py` (new) — Tier A + Tier B universes (commit 3).
5. `backend/tests/test_validate.py` (extend) — strict `$schema_version == x-version` remains enforced; v1.6 old-shape files pass during expand; no per-version gate is introduced (commit 3).
6. `backend/tests/test_inventory_derive.py` (new) — derivation determinism, observed/pending detection, zero vs null collection semantics, structured unavailable subtraction, status states, universe `$ref`, and operator-flag preservation (commit 4).
7. `backend/tests/test_period_sets.py` (new) — explicit periods, integer ranges/lists, string lists, and non-inferable/ad-hoc periods validate; no helper parses citizen labels into canonical dates (commit 4/5).
8. `backend/tests/test_indicator_migration.py` (new) — migration is idempotent, sidecar fields are preserved inline, pathspec output is POSIX-relative, and second run makes no changes (commit 5/6).
9. `backend/tests/test_coverage_emits_inventory.py` (new) — CLI integration, byte-identical re-runs after inventory refresh is wired (commit 8).
10. `backend/tests/test_admin_inventory_indicators.py` (new) — `/api/inventory/indicators` endpoint returns expected shape (commit 8).
11. `backend/tests/test_datasets_integrity.py` (extend) — all indicators are v2.0 after contraction; no `.notes.json` files survive; provenance cross-check; `indicator-inventory.json` covers every indicator path (commit 7/9).

### Frontend (vitest)

12. `frontend/src/contracts/datasets-conform.test.ts` (extend) — all v2.0 indicators and `reference/in/indicator-inventory.json` validate (commit 9).
13. `frontend/src/lib/indicator.test.ts` (extend or new) — loader parses folded v2.0 shape, rows remain long-form, period labels display verbatim (commit 9).
14. `frontend/src/lib/indicatorInventory.test.ts` (new) — static index loader parses all rows and exposes no directory-listing dependency (commit 9).
15. `frontend/src/lib/AboutThisData.test.ts` (new) — renders compact/full modes, hides empty sections, displays pending labels verbatim, uses "Collected from source on" copy (commit 10).

### Frontend e2e (Playwright)

16. `frontend/e2e/golden-path.spec.ts` (extend) — "About this data" renders; one provenance assertion; no new console errors/404s (commit 10).
17. `frontend/e2e/data-completeness.spec.ts` (new) — route loads from static index, table has all indicators, at least one stub/scope-unverified row visible, no console error, no horizontal overflow at mobile width (commit 10).

### Admin e2e (Playwright)

18. `admin/e2e/indicators-panel.spec.ts` (new) — existing shell loads, indicator panel renders, table sorts/filters, no console error (commit 10).

**All must be green at PR merge** (CLAUDE.md §9).

---

## §10. Memory updates (`/memories/`)

### §10.1 PREPEND to `/memories/lessons.md` (keep all prior entries):

```
Lesson (2026-05-17, yen-gov folded-indicator + collection-inventory):

Landed on a folded model — one JSON per indicator carrying the existing `indicator + rows[] + license + coverage + sources` contract plus `methodology + series_spec + collection_inventory + divergence` inline. NO sidecars. Schema migration uses expand -> migrate -> contract: v1.5 -> v1.6 optional folded fields, migrate all indicators and sidecars losslessly, then v1.6 -> v2.0 required folded fields. The 10 existing `.notes.json` sidecars are folded into typed inline fields (`related_indicators`, `editor_note_md`, `policy_context`, `chart_defaults`) and deleted.

Rejected designs (do NOT re-propose; full archive in TODO/20260517-folded-indicator-and-collection-inventory-handover.md §12):
1. SHA-gate at Fetcher + .meta.json sidecar — bytes ≠ data.
2. write_text_if_changed helper — same hash check in disguise.
3. Two-flag refetch — rm IS the force mechanism.
4. Fetcher freeze-guard — wrong layer.
5. Global mutable _inventory.json — underscore signals second-class; inventory truth is first-class inline. Static `datasets/reference/in/indicator-inventory.json` is allowed as a generated public index.
6. fetched_at rename — name is fine; glossary fixes meaning.
7. Structured ISO reference_period — heuristic; lossy.
8. Partial Max backfill — creates silent two-tier; all indicators migrate before contraction to v2.0.
9. Per-indicator .data-card.json sidecar — smushes lifecycles; fold instead.
10. ISO-normalised pending_periods[] — Indian publisher vocabularies (`as on 31.03.2025`, `Census 2011`, `FY 2024-25`) don't fit; any normaliser hits the LLM trap; ship `{key, label, frequency}` period-token round-trip.
11. `geographic_universe` / `universe` naming — academic jargon, collision-prone. Resolved: `expected_geographies` + `expected_periods`.

Key principles forced by the design loop:
- **Adapter owns its source's vocabulary; planner round-trips opaquely; citizen reads as-is.** No normaliser anywhere. Adapter MUST write citizen-readable labels (doc rule, not validator rule).
- **Period model has two explicit expected tracks plus observed state.** `series_spec.expected_periods` is the materialized obligation list; `series_spec.expected_periods_inference` explains whether it came from a publisher catalogue, source schedule, observed rows, or a non-inferable/ad-hoc source; `collection_inventory.observed_periods` is derived from `rows[]`.
- **Inventory derived, not stored separately.** `collection_inventory` block reflects (series_spec + rows on disk + sources). No parallel mutable state file. The public static `indicator-inventory.json` is a generated navigation/completeness index, not a source of truth.
- **Planner reads exactly three fields per indicator:** `frozen`, `refetch_requested`, `pending_periods`. Discipline forces minimal coupling. `refetch_requested` is triage/status in this PR, not a second force-recollect mechanism.
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

- Every indicator at datasets/indicators/in/<topic>/<id>.json is a single folded file: existing indicator + rows[] + license + coverage + sources, plus methodology + series_spec + collection_inventory + divergence.
- Schema: datasets/schemas/indicator.schema.json @ x-version 2.0.
- Geography sets: datasets/reference/in/universes.json (convenience; inline arrays also allowed).
- Derivation: backend/yen_gov/inventory/derive.py. Wired into the appropriate backend emit/coverage refresh point after pure derivation tests land.
- Migration overlays: typed one-shot overlay inputs for methodology and expected geographies; if retained after migration, they live under `datasets/reference/` or `config/` with schemas and `sources`.
- Frontend: AboutThisData.svelte on every indicator page; `/data-completeness` route backed by static `datasets/reference/in/indicator-inventory.json`.
- Admin: `/api/inventory/indicators` endpoint + Indicators panel (sibling to existing election Inventory in the admin shell).
- Fetch-once-freeze working contract: CLAUDE.md §10. rm is the only force-recollect.
- Adapter owns period-label vocabulary. Planner round-trips `{key, label, frequency}` opaquely. No normaliser, no LLM.
- Planner reads only: frozen, refetch_requested, pending_periods.
- Sidecar .notes.json files deleted in migration; content folded into typed inline methodology fields, not flattened into notes[].
```

---

## §11. Files-touched master table

| Layer | File | Action | Commit |
|---|---|---|---|
| Backend core | `backend/yen_gov/coverage.py` | Modify | 1, 8 |
| Backend core | `backend/yen_gov/coverage_indicator_pages.py` | Modify | 1 |
| Backend core | `backend/yen_gov/cli.py` | Modify | 8 |
| Backend core | `backend/yen_gov/validate.py` (or equivalent) | Modify only if schema resolution needs no-gate tests; keep strict equality | 3, 7 |
| Backend sources | `backend/yen_gov/sources/iced_state_wise/ingest.py` | Modify | 1 |
| Backend composers | `backend/yen_gov/composers/energy_capacity_by_source.py` | Modify | 2 |
| Backend inventory | `backend/yen_gov/inventory/__init__.py` | Create | 4 |
| Backend inventory | `backend/yen_gov/inventory/derive.py` | Create | 4 |
| Backend inventory | `backend/yen_gov/inventory/detect_cells.py` | Create | 4 |
| Backend inventory | `backend/yen_gov/inventory/diff_expected.py` | Create | 4 |
| Backend inventory | `backend/yen_gov/inventory/overlay.py` | Create | 4 |
| Backend inventory | typed migration overlay input(s) | Create | 5 |
| Backend admin | `backend/yen_gov/admin/inventory.py` | Modify (add `/api/inventory/indicators`) | 8 |
| Backend AGENTS | `backend/yen_gov/AGENTS.md` | Modify with owning docs commit | 8-10 |
| Schemas | `datasets/schemas/indicator.schema.json` | Modify (v1.5 -> v1.6 optional; v1.6 -> v2.0 required) | 3, 7 |
| Schemas | `datasets/schemas/indicator-notes.schema.json` | DELETE | 7 |
| Schemas | `datasets/schemas/universes.schema.json` | Create | 3 |
| Schemas | `datasets/schemas/indicator-inventory.schema.json` | Create | 9 |
| Reference data | `datasets/reference/in/universes.json` | Create | 3 |
| Reference data | `datasets/reference/in/indicator-inventory.json` | Create/generated | 9 |
| Indicators | `datasets/indicators/in/**/*.json` (all) | Modify (v1.6 expand/migrate, then v2.0 contract) | 3, 6, 7 |
| Indicators | `datasets/indicators/in/**/*.notes.json` (×10) | DELETE | 6 |
| Frontend lib | existing indicator loader/type module (e.g. `frontend/src/lib/indicators.ts`) | Modify/extend | 9 |
| Frontend lib | `frontend/src/lib/indicatorInventory.ts` | Create | 9 |
| Frontend lib | `frontend/src/lib/AboutThisData.svelte` | Create | 10 |
| Frontend routes | `frontend/src/routes/DataCompleteness.svelte` | Create | 10 |
| Frontend routes | `frontend/src/routes/About.svelte` | Modify with owning UI/docs commit | 10 |
| Frontend routes | `frontend/src/routes/Disclaimer.svelte` | Modify with owning UI/docs commit | 10 |
| Frontend integration | indicator card/detail/topic surfaces | Modify | 10 |
| Frontend routes registry | `frontend/src/main.ts` and `frontend/src/lib/url.ts` | Modify | 10 |
| Admin panel | `admin/src/routes/Indicators.svelte` or local panel component | Create | 10 |
| Admin shell | `admin/src/App.svelte` | Modify panel union/nav | 10 |
| Admin lib | `admin/src/lib/api.ts` | Modify (add indicator inventory client) | 10 |
| Admin routes | `admin/src/routes/Pipeline.svelte` | Modify only if stale `.runtime/` copy is user-visible | 10 |
| Admin routes | `admin/src/routes/EciRecon.svelte` | Modify only if stale `.runtime/` copy is user-visible | 10 |
| Tests backend | `backend/tests/test_coverage_idempotent.py` | Create | 1 |
| Tests backend | `backend/tests/test_energy_capacity_composer.py` | Extend | 2 |
| Tests backend | `backend/tests/test_indicator_schema.py` | Create/extend | 3 |
| Tests backend | `backend/tests/test_universes_schema.py` | Create | 3 |
| Tests backend | `backend/tests/test_validate.py` | Extend | 3, 7 |
| Tests backend | `backend/tests/test_inventory_derive.py` | Create | 4 |
| Tests backend | `backend/tests/test_period_sets.py` | Create | 4, 5 |
| Tests backend | `backend/tests/test_indicator_migration.py` | Create | 5, 6 |
| Tests backend | `backend/tests/test_coverage_emits_inventory.py` | Create | 8 |
| Tests backend | `backend/tests/test_admin_inventory_indicators.py` | Create | 8 |
| Tests backend | `backend/tests/test_datasets_integrity.py` | Extend | 7, 9 |
| Tests frontend | `frontend/src/contracts/datasets-conform.test.ts` | Extend | 9 |
| Tests frontend | indicator loader tests | Create/extend | 9 |
| Tests frontend | `frontend/src/lib/indicatorInventory.test.ts` | Create | 9 |
| Tests frontend | `frontend/src/lib/AboutThisData.test.ts` | Create | 10 |
| Tests frontend e2e | `frontend/e2e/golden-path.spec.ts` | Extend | 10 |
| Tests frontend e2e | `frontend/e2e/data-completeness.spec.ts` | Create | 10 |
| Tests admin e2e | `admin/e2e/indicators-panel.spec.ts` | Create | 10 |
| Docs concepts | `docs/concepts/folded-indicator.md` | Create with schema commit | 3/7 |
| Docs concepts | `docs/concepts/collection-inventory.md` | Create with derivation commit | 4 |
| Docs concepts | `docs/concepts/data-quality.md` | Create with UI/copy commit | 10 |
| Docs architecture | `docs/architecture/decisions/0003-no-fetch-cache.md` | Modify with collect/planner behavior commit | 8 |
| Docs how-to | `docs/how-to/force-recollect.md` | Create only if force-recollect docs remain needed | 8 |
| Docs root | `CLAUDE.md` | Modify with owning behavior/schema commit | 1, 8 |
| Docs root | `README.md` | Modify with UI route commit | 10 |
| Tools | `tools/migrate_indicators_v15_to_v20.py` | Create | 5 |
| Memory | `/memories/lessons.md` | Prepend after implementation (via memory tool) | 10 |
| Memory | `/memories/repo/yen-gov-architecture.md` | Append after implementation (via memory tool) | 10 |

---

## §12. Rejected designs archive (read if tempted to re-propose)

| # | Design | Status | Why rejected |
|---|---|---|---|
| 1 | SHA-gate at `Fetcher.fetch` + `.runtime/raw/<path>.meta.json` sidecar storing `{content_sha256, first_fetched_at, etag, last_modified}`. On re-fetch, if body SHA matches, reuse `first_fetched_at`. | REJECTED 2026-05-16 | Hashing every fetch is wasted compute. A decimal-precision flip ($1.00 vs $1.0000), comma vs period decimal separator, trailing-newline change — all flip the hash without changing the data. Hash equality is the wrong signal. Sidecar parallel-registry creates divergence-bug surface. |
| 2 | `write_text_if_changed(path, text)` helper — read existing, byte-compare, skip write if identical. | REJECTED 2026-05-16 | Same hash check in disguise. JSON pretty-print reorder, indent change, trailing newline all look "different" and rewrite. Papers over the real bug (`datetime.now()` leaking into content). CLAUDE.md §5 violation. **Structural fix:** remove `datetime.now()` from derived outputs so re-runs produce byte-identical output by construction. |
| 3 | Two-flag force-refetch (`--refetch --confirm-refetch`). | REJECTED 2026-05-17 | Gimmicky. `rm .runtime/raw/<path>` IS the force mechanism. Filesystem IS the cache. Deletion IS the override. |
| 4 | Fetcher-level freeze guard ("if raw file exists, return cached bytes; never hit network"). | REJECTED 2026-05-17 | Wrong layer. The right question is asked **upstream** by the ingest layer against the inventory: "do we already have data for indicator X period Y?" Fetcher never needs a guard because nothing calls it for already-collected cells. "Refetch" is the wrong word — we COLLECT MORE. |
| 5 | Global `datasets/_inventory.json` (single file listing all collected/pending URLs as mutable state). | REJECTED 2026-05-17 | Underscore prefix signals "machine-only / second-class." Inventory truth is first-class, per-indicator, inline. Allowed replacement: schema-validated static `datasets/reference/in/indicator-inventory.json` generated from committed indicators for public navigation/completeness. |
| 6 | Rename `fetched_at` → `snapshot_taken`. | REJECTED 2026-05-17 | "`fetched_at` is not a terrible name" (user verbatim). Glossary fixes meaning, not a mass rename. |
| 7 | Structured `reference_period` field (ISO 8601 interval). | REJECTED 2026-05-17 | Requires heuristic conversion. Lossy. No consumer needs structure. Publisher's free-text IS the truth. |
| 8 | Partial Max backfill (data-card for 15-20 indicators, rest unauthored). | REJECTED 2026-05-17 | Silent two-tier quality. "All or none." **Resolution:** auto-generate structural fields for ALL 106; methodology hand-authored where known, empty arrays elsewhere, dashboard flags stubs loudly. |
| 9 | Per-indicator `.data-card.json` sidecar. | REJECTED 2026-05-17 | Smushes lifecycles. User: "no sidecars, no extras, no ceremonies." Fold methodology + inventory inline. |
| 10 | ISO-8601-normalised `pending_periods[]`. | REJECTED 2026-05-17 (Hans+Max+Fowler debate) | Indian publisher vocabularies (`as on 31.03.2025`, `Census 2011`, `FY 2024-25`, `Q3 FY25`) don't fit cleanly. Any normaliser will reach for an LLM. LLM-in-build-step is non-deterministic dependency we will regret. **Resolution:** `{key, label, frequency}` period-token round-trip; nothing parses; adapter owns vocabulary end-to-end. |
| 11 | `geographic_universe` / `universe` field naming. | REJECTED 2026-05-17 (Hans+Max+Fowler debate) | Academic jargon. No international-catalogue precedent (FRED uses `geo`/`time_period`; OWID uses `dimensions`; Eurostat uses `geo`/`time_period`). Collision-prone with future fields. **Resolution:** `expected_geographies` + `expected_periods` — explicit obligation, citizen-readable, hard to want elsewhere. `coverage.spatial` / `coverage.temporal` keep their role as editorial-prose siblings. |

For composer dedup `(url, fetched_at) → url`: keep **earliest** `fetched_at` because it's the more conservative claim about "when we first saw this URL." With fetch-once-freeze enforced from commit 1 onwards, all entries for a URL share one `fetched_at` anyway; the earliest-keep rule is defensive cleanup of historical duplicates already on disk.

---

## §13. Deferred follow-ons (explicit non-goals, rationale documented)

These are intentionally NOT in this PR. Each has a rationale. None are blockers.

1. **Adapter `source_capability.available_periods[]` declaration** (phase 2 of three-way intersection). Strangler-fig: this PR's emit layer assumes adapters cover full `series_spec`; future PR lets adapters opt in to declaring capability, emit-layer intersects three sets, residue -> structured `unavailable_periods` / "Not published by source" with adapter-supplied reason. Same `{key, label, frequency}` token shape both sides.
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

- [ ] All 10 amended commits made; two-hat discipline preserved (structural != behavioural).
- [ ] `pytest -q` green in `backend/`.
- [ ] `npm test` green in `frontend/`.
- [ ] `npm run test:e2e` green in `frontend/`.
- [ ] `npm run test:e2e` green in `admin/` (if e2e command exists; otherwise smoke-tested per §13).
- [ ] `python -m yen_gov coverage; git status` -> clean after inventory refresh is wired (commits 1 + 8 working as designed).
- [ ] Re-run `python -m yen_gov coverage` immediately again -> still clean.
- [ ] No `[DEBUG]` markers in code (CLAUDE.md §7).
- [ ] No new hardcoded magic strings/numbers (CLAUDE.md §6, §10).
- [ ] No new mocks beyond the rare ones explicitly listed in CLAUDE.md §15.
- [ ] `bun install` run in `frontend/` AND `admin/` if either `package.json` touched; both `bun.lock` files staged in the same commits (CLAUDE.md §9).
- [ ] Browser-tool UI verification done per CLAUDE.md §13; routes verified noted in commit 10 message.
- [ ] Memory files updated (`/memories/lessons.md` prepended, `/memories/repo/yen-gov-architecture.md` appended).
- [ ] `docs/concepts/`, `docs/architecture/decisions/`, `docs/how-to/`, `CLAUDE.md`, `README.md`, backend `AGENTS.md` updated in the same commits as the behavior/contracts they document.
- [ ] No `.notes.json` files survive under `datasets/indicators/`.
- [ ] `datasets/schemas/indicator-notes.schema.json` deleted.
- [ ] No temporary per-version validator gate exists; strict `$schema_version == x-version` is still enforced in backend and frontend contract tests.
- [ ] `datasets/reference/in/indicator-inventory.json` exists, validates, and covers every committed indicator path.
- [ ] PR description summarises: original bug + structural fix; folded model + v2.0 schema; 106 migrations; new public route; new admin panel; explicit deferred list (§13).

---

## §15. Invocation phrase for the next agent

> "Read `TODO/20260517-folded-indicator-and-collection-inventory-handover.md` end-to-end, especially §3.3. Execute the amended 10-commit slate in §4 in order. Honour the working contract in §2 and the critical amendments in §3.3 — do NOT relitigate rejected designs. If anything is ambiguous, surface it to the user; do not guess. Run the §14 pre-flight checklist before opening the PR."

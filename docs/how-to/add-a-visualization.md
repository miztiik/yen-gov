# How to add a visualization

**Last Updated**: 2026-05-11
**Audience**: contributors adding a new chart, map, or panel to the static frontend.
**See also**: [docs/architecture/frontend/overview.md](../architecture/frontend/overview.md), [docs/architecture/frontend/indicators.md](../architecture/frontend/indicators.md), [docs/architecture/frontend/colours.md](../architecture/frontend/colours.md), [docs/architecture/frontend/data-loading.md](../architecture/frontend/data-loading.md), [docs/concepts/data-provenance.md](../concepts/data-provenance.md).

This is the path of least resistance for a contributor. Follow it and your visualization will already obey the holy laws (CLAUDE.md §1) — schema-first, no hardcoding, provenance visible, no runtime backend.

---

## 1. Decide what kind of visualization you need

Three buckets, three different paths:

| Kind | Examples | Path |
| --- | --- | --- |
| **Indicator view** (one number per state, possibly time-series) | per-capita NSDP, literacy %, installed MW | use the existing primitives — see §2 |
| **Election view** (party / candidate / constituency facts for a single event) | seats donut, margin histogram, AC stacked bar | new bespoke Svelte component — see §3 |
| **Cross-cutting query** (joins across files / arbitrary SQL) | "every AC where the winner won by < 1%" | extend `/explore` (sql.js / sqlite-wasm) — see §4 |

If your data fits the **indicator** bucket, you almost never need new component code. The metadata-driven primitives ([`IndicatorChoropleth`](../../frontend/src/lib/IndicatorChoropleth.svelte), [`IndicatorRanked`](../../frontend/src/lib/IndicatorRanked.svelte), [`IndicatorSmallMultiples`](../../frontend/src/lib/IndicatorSmallMultiples.svelte)) read everything they need from the artifact's `value_kind` / `direction` / `comparability` / `scale_hint` fields. Adding a new indicator is a backend ingest job + one line to wire it into [`StateOverview.svelte`](../../frontend/src/routes/StateOverview.svelte).

---

## 2. Indicator view — the metadata-driven path

### 2a. Land the data first

A visualization without its data is a band-aid (CLAUDE.md §1.5). Land the artifact under `datasets/indicators/in/<category>/<slug>.json` first, validating against [`indicator.schema.json`](../../datasets/schemas/indicator.schema.json):

```bash
python -m yen_gov validate
```

Required honesty fields (indicator schema v1.1+): `value_kind`, `direction`, `comparability`, `series_breaks`, `methodology_vintage`, `attribution_geography`, `redistributable`, plus the mandatory `sources[]` (CLAUDE.md §12). If you don't know one of these, the answer is "go read the source", not "leave it null". See [docs/architecture/frontend/indicators.md](../architecture/frontend/indicators.md) for what each field controls in the UI.

### 2b. Wire it into a route

Open [`frontend/src/routes/StateOverview.svelte`](../../frontend/src/routes/StateOverview.svelte) and add a section in the "National context" block:

```svelte
<IndicatorChoropleth
  artifact="indicators/in/<category>/<slug>.json"
  home_state={state_code}
/>
<IndicatorRanked
  artifact="indicators/in/<category>/<slug>.json"
  home_state={state_code}
/>
```

That's it. The component reads the artifact, picks the colour ramp from `direction`, picks the number formatter from `value_kind`, picks the legend scale from `scale_hint`, suppresses the rank when `comparability=not_comparable_across_states`, renders the source list, and shows the methodology-vintage chip. **Do not** subclass or wrap these to add per-indicator special cases — every special case is a missing field in the schema. If the data needs different rendering, the schema needs a new field; bump it (CLAUDE.md §11) and update the primitive once for everyone.

### 2c. Check it

```bash
cd frontend
bun run check    # svelte-check (types)
bun run test     # vitest (pure helpers)
bun run dev      # browse to http://127.0.0.1:5173/s/tamil-nadu
```

If you added a new helper alongside the indicator (e.g. a new derived statistic), add a vitest case in [`frontend/src/lib/indicators.test.ts`](../../frontend/src/lib/indicators.test.ts).

---

## 3. Election view — bespoke component

This path is for charts that are **not** generic across indicators: AC-level vote share bars, party-specific margin distributions, swing maps. Expect to write Svelte.

### 3a. Find your data shape

Election artifacts already have schemas under [`datasets/schemas/`](../../datasets/schemas/). The frontend's typed views are in [`frontend/src/lib/data.ts`](../../frontend/src/lib/data.ts). If you need a field that isn't on the typed view yet, add it to the TypeScript interface **and** verify it's in the schema — the two must agree (the test [`backend/tests/test_core_models.py`](../../backend/tests/test_core_models.py) catches drift between the JSON Schemas and the Python mirrors; the TypeScript side is by manual review).

### 3b. Write the component

Conventions, all enforced by existing components — read one before writing yours:

| Concern | Convention | Reference |
| --- | --- | --- |
| Colour | Always go through `colors.forSet(codes)` for multi-party charts; `colors.fill(code, short)` only when a single colour is needed in isolation. Never hardcode hex. | [colours.md](../architecture/frontend/colours.md), [`PartyBar.svelte`](../../frontend/src/lib/PartyBar.svelte) |
| Map | Extend `MapChoropleth` or compose a new file under `frontend/src/lib/maplibre/`. Boundary sources resolve through [`maplibre/sources.ts`](../../frontend/src/lib/maplibre/sources.ts) — local snapshots first, upstream URL last-resort only. | [map.md](../architecture/frontend/map.md), [`StateAcMap.svelte`](../../frontend/src/lib/maplibre/StateAcMap.svelte) |
| Tooltip | Use [`ChartTooltip.svelte`](../../frontend/src/lib/ChartTooltip.svelte) — it handles positioning, viewport clipping, and touch. | [`MarginHistogram.svelte`](../../frontend/src/lib/MarginHistogram.svelte) |
| Provenance | Mount `<SourceList sources={…} schema_version={…} />` in the same card. Non-negotiable (CLAUDE.md §12). | [`SourceList.svelte`](../../frontend/src/lib/SourceList.svelte) |
| URL building | Use the `url` helper. Never write `\`/s/${...}\`` inline. | [`frontend/src/lib/url.ts`](../../frontend/src/lib/url.ts) |
| State (signals) | Svelte 5 runes (`$state`, `$derived`, `$effect`). Resolve params via the reactive `states` store, not by parsing the slug yourself. | [`StateOverview.svelte`](../../frontend/src/routes/StateOverview.svelte) |
| Loading / error | Three-state render: `state_code unknown` → "Resolving…", `error` → red banner, `!data` → "Loading…", else the chart. Don't render half-loaded views. | every route file |

### 3c. Mount it

If it belongs on an existing page, drop it into the route file. If it's a whole new page:

1. Add the route in `frontend/src/main.ts` and the router (see [`frontend/src/lib/router.svelte.ts`](../../frontend/src/lib/router.svelte.ts)).
2. Add a `url.<thing>(…)` helper in [`url.ts`](../../frontend/src/lib/url.ts).
3. Link to it from the relevant existing page — orphan routes fail silently.

### 3d. Test it

```bash
bun run check
bun run test
bun run test:e2e   # adds the new path to the golden-path suite if you extend it
```

Pure helpers belong in vitest (`*.test.ts` colocated with the source). End-to-end paths go in [`frontend/e2e/golden-path.spec.ts`](../../frontend/e2e/golden-path.spec.ts) — only add a case if the new view is on the citizen's first-visit critical path.

---

## 4. Cross-cutting query — extending `/explore`

The Explore route lazy-loads `sql.js` and queries the per-state `results.sqlite` snapshot ([`docs/reference/sqlite-schema.md`](../reference/sqlite-schema.md), ADR-0014). To add a new prebuilt query:

1. Add the SQL + a one-line label under `frontend/src/lib/explore/`.
2. The Explore route picks it up automatically.
3. **Do not** make any other route depend on sqlite-wasm. The lazy-load decision is route-scoped (locked decision, 2026-05-08): only `/explore` may pull the wasm chunk.

If your query needs data that isn't in `results.sqlite`, the SQLite emitter under `backend/yen_gov/emit/` is the place to add it — never compute derived columns in the browser to fill gaps in the file.

---

## 5. Definition of done

Per CLAUDE.md §9 the change is not done until **all** hold:

- [ ] Schema bumped if any persisted contract changed; `x-changelog` entry added in the same commit.
- [ ] Data file (if any) carries `sources[]` and validates clean (`python -m yen_gov validate`).
- [ ] `bun run check` clean (no Svelte / TS errors).
- [ ] `bun run test` clean (vitest).
- [ ] `bun run test:e2e` clean if the visualization is on a route covered by the golden-path harness.
- [ ] Provenance visible in the rendered UI (`<SourceList>` mounted near the chart).
- [ ] No `[DEBUG]` markers (CLAUDE.md §7).
- [ ] No new hardcoded colours, magic numbers, or per-indicator special cases (CLAUDE.md §10).
- [ ] Architecture doc under `docs/architecture/frontend/` updated if the visualization introduces a new pattern, primitive, or invariant. A code commit without its rationale doc is incomplete (CLAUDE.md §1.4).

---

## 6. Common pitfalls (read before starting)

- **Don't wrap a primitive to special-case one indicator.** That's a missing schema field. Bump the schema; update the primitive once.
- **Don't fetch from `https://...`** at runtime. Bundle is same-origin only (CLAUDE.md §1, ADR-0013). All data goes under `/data/`.
- **Don't compute colours inline.** Two charts on the same page with the same parties must share hues — that requires `colors.forSet`, not per-component `colors.fill` ([colours.md](../architecture/frontend/colours.md)).
- **Don't treat `params.state` as an ECI code.** It's a slug. Resolve via `states.codeFromSlug(params.state)`.
- **Don't render before `state_code` is non-null.** The slug → ECI resolution is async on first load; rendering early either crashes (no `STATE_AC[undefined]`) or silently fetches `/data/elections/.../undefined/...`.
- **Don't paste a static legend.** Drive it from `value_kind` + `direction` + the data's actual range. Static legends lie when the data updates.

# Per-indicator documentation pages — structural plan

**Created**: 2026-05-15
**Status**: design locked (Max + Hans concurred); ready for execution
**Trigger**: ~102 indicators today, heading to ~150–200; mega-tables in [data-inventory.md](../docs/reference/data-inventory.md) hit their per-topic limit (energy 37 rows post-Tier-3); narrative prose in [data-coverage-report.md](../docs/reference/data-coverage-report.md) cannot scale; per-indicator depth (methodology vintage, series_breaks, comparability scope, denominator definition, what's-NOT-counted, RE/BE revision tier, citizen-readable framing) is buried in artifact JSON or batch prose.

## Design (Max + Hans synthesis, 2026-05-15)

### Three doc tiers, each one job

| Surface | Job | Granularity | Maintenance | Location |
| --- | --- | --- | --- | --- |
| **Inventory** (existing, slimmed) | Breadth: "what indicators exist?" | One row per indicator per topic | **Auto** | [docs/reference/data-inventory.md](../docs/reference/data-inventory.md) |
| **Per-indicator page** (NEW) | Depth: "what does THIS indicator mean?" | One file per indicator | **Auto from artifact + optional sidecar** | `docs/reference/indicators/<topic>/<id_basename>.md` |
| **Topic spine** (NEW) | Shared methodology: "how RBI organises state finances", "WPI vs CPI-IW vs CPI-Combined", "ICED vs CEA division of labour", "SRS sample frame" | One file per topic | **Hand** | `docs/reference/topics/<topic>.md` |
| **Coverage report** (existing, slimmed) | Narrative: batch ingest stories, deferred candidates, gap-list, derived views, mis-framing debt | Source-batch / pillar prose | **Hand** | [docs/reference/data-coverage-report.md](../docs/reference/data-coverage-report.md) |

### Per-indicator page template (auto-rendered from artifact)

Path: `docs/reference/indicators/<topic>/<id_basename>.md` mirrors `datasets/indicators/in/<topic>/<id_basename>.json` 1:1.

```markdown
# <topic>/<id>

**Title**: <indicator.title>
**One-line**: <derived from indicator.description first sentence>
**Last Updated**: <UTC stamp> (auto-generated)

## Definition
<indicator.description verbatim>

## Signature
| Field | Value |
| --- | --- |
| entity_kind | … |
| time_grain | … |
| value_kind | … |
| unit | … |
| direction | … |
| comparability | … (4-level enum, see Hans §5) |
| attribution_geography | … |
| implementing_authority | … |

## Coverage
- **Temporal**: <span> (<n> periods) — Temporal Richness <meter>
- **Spatial**: <n entities>
- **Per-entity matrix**: <auto: entity_id × Temporal Richness>

## Methodology vintage
<indicator.methodology_vintage>

## Series breaks
| at_time | kind | note |
| ... |

> Renderer guard: <renderer_rules[] verbatim, e.g. "growth rates spanning a `definition_change` break MUST NOT be computed">

## Revision tier (Hans field — fiscal/SRS only)
| from | tier | note |
| ... |

## Denominator (Hans field — ratios only)
| field | value |
| --- | --- |
| what | GSDP |
| price_basis | current |
| base_year | 2011-12 |
| source_artifact | <link> |

## What's NOT counted (Hans field)
- e.g. "IGNOAPS / IGNWPS social pensions excluded"
- e.g. "rural housing not collected by NSO"

## Policy context (Hans field — sidecar-curated)
- 1–3 bullets linking to the policy debate the indicator is read inside.

## Chart defaults
direction · scale_hint · faceting · allowed-negative semantics.

## Related indicators
- <auto from sidecar.related[] or topic-catalogue cross-edges>

## Sources
<indicator.sources[] with full url + fetched_at + producer name>

## License
<indicator.license object>

## Citation (auto-generated, journalist-pasteable)
> <Producer>, *<Publication>*, Table <n>. Re-published by yen-gov as `<id>`, schema v<x.y>. Retrieved via yen-gov pipeline on <YYYY-MM-DD>.

## Schema
indicator.schema.json v<x.y> · artifact: [<path>](<path>)
```

### Generation strategy — hybrid with thin seam

- **Auto from artifact** (95%): every section above except *Related indicators*, *Editor's note*, *Policy context*. The artifact already carries the rest in `indicator.*`, `series_breaks`, `coverage`, `sources`, `license`.
- **Optional sidecar** at `datasets/indicators/in/<topic>/<id>.notes.json` — schema-validated, all fields optional:
  ```json
  { "$schema_version": "1.0",
    "related": ["economy/state_nsdp_current_inr_crore"],
    "editor_note_md": "Pair with single-base ICED siblings when single-base purity matters.",
    "policy_context": ["Old Pension Scheme restoration debate; NPS adoption dates by state"],
    "chart_defaults": { "preferred_facet": null, "allowed_negative": false } }
  ```
  Sidecar absent ⇒ corresponding sections omitted from page. The seam is intentional: *Related* is a graph-edge that doesn't belong inside any single artifact's authoritative metadata; *editor_note* is the one place a human voice belongs.

- **`python -m yen_gov coverage` learns one new sub-command**:
  ```
  python -m yen_gov coverage indicator-pages   # writes docs/reference/indicators/**
  python -m yen_gov coverage                   # also re-runs the above
  ```
  Both produce auto-generated banner + UTC `Last Updated` stamp; CI fails if the tree drifts from the artifacts (same pattern as the existing inventory).

### Index / navigation (no third index)

- **`docs/reference/data-inventory.md` stays the breadth index** — each row's `id` cell becomes a markdown link to its per-indicator page. Citizens / agents already land here; no new front door.
- **`docs/reference/indicators/index.md` (NEW)** — auto-generated alphabetical + by-topic listing, one line per indicator (`id — one-line definition — span — Wired?`). OWID `/data` equivalent; useful when a user knows the topic but not the table layout.

### Comparability ladder — fixed 4-level enum (Hans §5)

Replace the current 2-value comparability with:

| Level | Token | Citizen-readable gloss |
| --- | --- | --- |
| 1 | `comparable_across_states_and_time` | "Rank states; trace trends." |
| 2 | `comparable_across_states_snapshot_only` | "Rank states **today**; do NOT trace trends." (HDI 2011 vs 2017.) |
| 3 | `comparable_within_state_over_time` | "Trace one state over time; do NOT rank states." |
| 4 | `directional_only` | "Read direction-of-change only; magnitudes are noisy." (WPI across 5 base splices.) |

Today's `comparable_with_normalisation` is too vague — splits into level 2 / 3 / 4 depending on what the missing normalisation actually is. Schema bump 1.4 → 1.5 (additive minor; old token deprecated with mapping rule, not removed).

### Topic spine pages (Hans §3 — shared methodology, NOT per-indicator repetition)

`docs/reference/topics/<topic>.md`, hand-written, ~1 page each. Initial four (highest leverage):

1. **`fiscal.md`** — RBI Statement numbering; A/RE/BE cycle; FC award windows; divisible-pool vs cess; when to read "states-combined" vs per-state.
2. **`prices.md`** — WPI vs CPI-IW vs CPI-Combined: which one for which question; rebase splices and renderer discipline.
3. **`health.md`** — SRS sample frame; calendar-year convention; AP/Telangana split treatment; why CDR is age-confounded.
4. **`energy.md`** — ICED vs CEA division of labour (long series vs freshness snapshot); generation vs procurement vs installed-capacity distinction; Tier-1/2/3 batch context.

Per-indicator pages link UP to the topic page rather than reproduce the paragraph. Holy Law #4 done right.

## Schema changes required (additive minor bumps only)

1. **`indicator.schema.json` v1.4 → v1.5** — additive minor:
   - `comparability` enum extended with the 4-level ladder; `comparable_with_normalisation` deprecated (kept valid; mapping rule documented in `x-changelog`).
   - `revision_tier_by_period[]` (optional array) — `[{ from: "2024-04", tier: "RE" }]`.
   - `denominator` (optional object) — `{ what, price_basis, base_year, source_artifact }`.
   - `excludes[]` (optional array of strings).
   - `renderer_rules[]` (optional array of slug-strings; controlled vocabulary in a sibling reference doc).
2. **`indicator-notes.schema.json` v1.0** (NEW, additive) — sidecar for hand-curated `related[]`, `editor_note_md`, `policy_context[]`, `chart_defaults`.

Backfill order (highest-leverage first):
- `fiscal/state_pension_expenditure_inr_crore` (RE/BE tier visible).
- `fiscal/outstanding_debt_pct_gsdp` (denominator visible).
- `economy/state_per_capita_nsdp_*` family (denominator visible).
- `prices/national_wpi_*` (renderer_rules visible).
- All ratio-typed indicators get `denominator` (currently ~12 indicators).

## Migration cost — honest

- **Zero touches to existing artifacts** for the page generator itself (everything needed is in v1.4).
- **One new generator** (~200 LOC in `backend/yen_gov/coverage/`).
- **One new optional schema** (`indicator-notes.schema.json`).
- **One new doc directory** (`docs/reference/indicators/`) — populated entirely by generator on first run; ~102 files materialise from one command.
- **Inventory generator change**: link the `id` column to per-indicator page (1-line edit).
- **Coverage report trim**: ~100 lines of per-indicator prose collapsed to one-liners + links. Hand work, bounded.
- **Schema 1.5 bump** is a separate Level-3 PR after the page generator ships — needed for the Hans governance fields, not for the page tree itself.
- **Topic spine pages** are 4 hand-written pages, ~1 day total.

Total: a Level-3 change (generator + thin sidecar schema + doc-tree + inventory linkifier + coverage-report trim).

## Anti-patterns (what NOT to do)

- **No per-state pages in `docs/`.** A "Tamil Nadu page" is a citizen-facing surface (`frontend/`), not docs. Per-state docs would duplicate the catalogue 36×.
- **No per-source pages in indicator tree.** `data-sources.md` already does the per-source narrative; doubling it would split provenance from the indicator.
- **No per-cohort election pages mixed in.** Elections live in `datasets/elections/` and are catalogued in `data-inventory.md §2`.
- **No `docs/reference/indicators/<topic>/<entity_kind>/<id>.md`.** Fourth level breaks `docs/` max-depth rule.
- **No hand-maintained per-indicator MD as primary artifact.** Hand-written pages will silently rot when the artifact is re-emitted with a new `methodology_vintage`. Sidecar is the only place hand-edits land.
- **No description duplication across batch report and indicator page.** Coverage report references each page by link; never re-states the definition.
- **Series breaks NEVER hidden behind tooltips / accordions.** The break is the headline, not the footnote — inline list, on the chart, in the inventory `breaks` column. Three places, same source-of-truth (`series_breaks[]`).
- **NO collapsing comparability to a single boolean.** The 4-level ladder is the minimum honest vocabulary for Indian data.
- **NO removing `denominator` / `excludes[]` / `policy_context[]` from per-indicator pages on the grounds that "it's in the topic page."** Topic page carries shared *methodology*; what a specific indicator excludes (IGNOAPS for pension; rural for housing CPI) is per-indicator, citizen-facing, and journalist-deep-link-friendly. Repetition across siblings is a feature when each page must stand alone.

## Phased execution plan (Fowler sequencing — expand-only)

- **Phase 1** (Level 3): Generator + topic-grouped index in one PR; pages exist, nothing points at them yet. Ships ~102 auto-generated pages in `docs/reference/indicators/`. No schema changes. No migration.
- **Phase 2** (Level 2): Inventory linkifier + coverage-report trim. Inventory rows' `id` cell becomes a link; coverage-report prose collapsed to one-liners.
- **Phase 3** (Level 3): Schema v1.5 bump (Hans governance fields). Backfill the 5 highest-leverage artifacts listed above. Per-indicator pages auto-pick up the new fields on next regeneration.
- **Phase 4** (Level 2): Sidecar schema 1.0 + first hand-curated `related[]` / `policy_context[]` for the energy + fiscal flagship indicators. Stops at "first ten"; rest accrue organically as researchers contribute.
- **Phase 5** (Level 2): Topic spine pages (`fiscal`, `prices`, `health`, `energy`). Per-indicator pages link UP.

Each phase is independently shippable. No phase requires the next.

## Source agent reports (for full rationale)

- **Max (Indicator Scout) — OWID/catalogue lens.** Full report in chat-session-resources for session 623d1121. Key insight: per-indicator pages auto-generated from the artifact, sidecar holds graph-edges (related, citation, editor note); inventory stays compact as breadth index.
- **Hans (Governance) — public-administration lens.** Full report in this session's chat. Key insight: governance fields (`revision_tier_by_period`, `denominator`, `excludes[]`, `policy_context[]`) are PER-indicator and CITIZEN-FACING — never hide behind tooltips, never collapse comparability to a boolean, never move per-indicator audit fields to topic page.

## Open follow-ups

- Bind `revision_tier_by_period[]` schema field. Confirm with Gregor before Phase 3.
- Confirm sidecar location: colocated (`datasets/indicators/in/<topic>/<id>.notes.json`) vs sibling tree (`datasets/indicators/notes/...`). Gregor decision.
- Confirm `renderer_rules[]` controlled vocabulary lives at `datasets/reference/in/renderer-rules.json` (matching pattern of party / topic / state registries).
- Topic-spine page outlines: who owns the first draft of each? (Hans for fiscal/health/prices; Max for energy seems natural.)

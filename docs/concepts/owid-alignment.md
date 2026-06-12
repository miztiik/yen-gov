# OWID alignment — fallback doctrine

**Last Updated**: 2026-06-12

## What this is

When a yen-gov design question on **URL shape, indicator identity, granularity, discoverability, or scalability** does not have a settled answer from a yen-gov doc, the fallback is: **do what Our World in Data does**.

Our World in Data (OWID) is the most successful long-running open dataset publisher in the same problem class as yen-gov: a static-bundle citizen-facing site, schema-first ingestion, multi-decade trajectory storytelling, methodology-stable comparability, every chart cite-able. They have shipped these decisions at ~10,000-indicator scale across 15+ years; the patterns are battle-tested at orders of magnitude beyond where yen-gov sits today.

This doctrine is not "copy OWID." It is **"default to OWID; document every divergence with a named reason."** Divergences are first-class — yen-gov is geography-first for an Indian-citizen audience, OWID is topic-first for a global-researcher audience — but each divergence carries a written rationale in the relevant ADR or subsystem doc.

## Why this earns its place

Without a fallback doctrine, every recurring design question (URL marker yes/no, indicator id shape, vintage placement, hierarchy display) re-debates the same trade-offs with different agent voices and slightly different framings. A fallback collapses the debate when there's no yen-gov-specific reason to reinvent. It also gives reviewers a concrete check: "does this match OWID? if not, where's the named reason?"

This pattern is itself OWID-style — they have a small set of public principles (`open`, `methodology-transparent`, `comparable`, `cite-able`) that resolve most internal disputes without re-debate.

## Where it applies

| Domain | OWID-canonical | yen-gov default |
|---|---|---|
| **Indicator URL slug** | Flat single segment (`/grapher/co2-emissions-per-capita`), not topic-hierarchy path | Flat single segment (`installed-capacity`) per [ADR-0028](../architecture/frontend/url-grammar.md#adr-0028-url-scheme-place-first-flat-indicator-slug). |
| **Indicator id (producer-side)** | `<topic>/<leaf>` or flat — internal namespace, not citizen surface; one id per measure, grain dispatched at render time | **ALIGNS** with OWID after [ADR-0044](indicator-naming.md#adr-0044-grain-over-entity) (2026-05-26): `<family>/<measure>-<unit>-<facet>` (`energy/installed-capacity-coal-mw`), one id spans `country` / `state` / `district` rows via `entity_kinds[]` on the catalogue row. Prior divergence (`state-`, `district-`, `national-` grain prefixes encoded into the id, ~77 sibling pairs across the corpus) RETIRED. |
| **URL routing mode** | Path-routed with SPA fallback (`/404.html → /index.html` on GitHub Pages or equivalent) | Path-routed per ADR-0028 (supersedes hash-routing ADR-0016). |
| **Topic-in-URL** | No. Topics live in IA (topic hubs, faceted search), not URL spine. URL stability beats taxonomy expressiveness. | No. ADR-0028. |
| **Vintage in URL** | No. Vintage is a UI control with sane default; `?` param only for citation. | No. ADR-0028. |
| **Indicator catalogue** | Single registry, every indicator carries provenance, methodology, comparability flags | `datasets/_ops/indicators-completeness.json` + per-indicator artifact carrying `methodology`, `series_breaks`, `comparability` (folded model per ADR-0026). |
| **Provenance** | Every chart cites its source; no anonymous data | Every artifact carries `sources[]` per CLAUDE.md §12. |
| **Schema versioning** | Additive when possible, breaking with migration. Schema-shape identity lives in the `.schema.json` file's own version; data emit files do NOT carry a top-level `$schema_version` stamp. Data-freshness pointers (`origin.date_accessed`), publisher edition tag (`origin.version_producer`), and refresh cadence (`dataset.update_period_days`) are separate semantic fields on the `origin.*` / `dataset.*` metadata blocks. | `x-version` major.minor with `x-changelog` per CLAUDE.md section 11; writer-strict / reader-compatible rollout per [ADR-0047](../architecture/data/schema-evolution.md#adr-0047-schema-version-compatibility-contract). **DIVERGES** on stamping: yen-gov currently stamps a top-level `$schema_version` semver on every JSON data emit file (in addition to the schema's `x-version`). Pending OWID-conformance pivot retires this stamp; see [Named divergence #5](#named-divergences-from-owid-with-reasons) and [schema-evolution.md §Pending OWID-conformance pivot](../architecture/data/schema-evolution.md#pending-owid-conformance-pivot-stop-stamping-schema_version-onto-data-emit-files). |
| **Granularity of an indicator** | One concept per chart; mixed units never share a Y-axis | One concept per artifact; composite-with-mixed-units uses `rows[].facet` + `rows[].unit` override per ADR-0026 / Phase 4 of the ICED plan. |
| **Methodology breaks** | Surfaced as chart annotations + banner | `series_breaks[]` on the artifact; rendered as banner chrome. |

## Named divergences from OWID (with reasons)

These are the places yen-gov **does not** match OWID, each with a written rationale:

1. **Geography in the URL path, not in `?country=`** (ADR-0028).
   OWID's primary audience is global researchers comparing many countries on one chart; their canonical URL is the chart, with countries as a query-string projection. yen-gov's primary audience is Indian citizens looking at "my place" first; the canonical URL is the place, with the indicator as a path leaf. Place-first IA is documented in [ADR-0022](place-first-ia.md#adr-0022-place-first-ia-with-topic-catalogue) and the [citizen-first doctrine](citizen-first.md).

2. **Static repo of typed JSON artifacts, not a Postgres-backed grapher engine** (CLAUDE.md Holy Law #1, ADR-0026).
   OWID runs a backend that serves chart data on demand. yen-gov has no production backend; everything ships in the bundle. Trade-off: yen-gov is smaller in scale and can afford full pre-emit; OWID at 10k indicators cannot.

3. **Indian publisher vocabulary preserved as-published, no canonical normaliser** (CLAUDE.md §10, [folded-indicator concept](folded-indicator.md)).
   OWID has a global canonical-form ISO period vocabulary. Indian publishers print `FY 2024-25`, `as on 31.03.2025`, `Census 2011` — yen-gov ships those labels verbatim through the adapter→planner→citizen chain. Documented in [collection-inventory](collection-inventory.md).

4. **Elections as one topic of many, not the lead surface** (repo memory `yen-gov-architecture.md`, ADR-0022).
   OWID doesn't have an election problem. yen-gov explicitly demotes elections from the cold-landing surface to keep socio-economic indicators (fiscal, education, health) first-class. User-mandated 2026-05-11.

5. **`$schema_version` stamped on every data emit file** (open divergence, pending pivot — 2026-06-12).
   OWID stamps schema identity only in the `.schema.json` file itself; data files don't carry a `$schema_version` sibling. yen-gov today stamps `$schema_version` at the top of every JSON artifact in `datasets/` (boundary SoT, manifest, taxonomy, indicators-completeness, etc.) populated from the schema's own `x-version`. The conflation is honest at the writer (the field is correctly semver, not a date), but it duplicates schema identity onto the data tier where OWID keeps schema identity, data freshness (`origin.date_accessed`), publisher edition (`origin.version_producer`), and refresh cadence (`dataset.update_period_days`) as four separate semantic concerns. User mandate 2026-06-12 ("no more calling it schema version" + "OWID conformance style") triggered the pivot. Tracked in [schema-evolution.md §Pending OWID-conformance pivot](../architecture/data/schema-evolution.md#pending-owid-conformance-pivot-stop-stamping-schema_version-onto-data-emit-files) + [TODO/20260612-schema-version-field-refactor-plan.md](../../TODO/20260612-schema-version-field-refactor-plan.md). When the pivot lands, this row moves OUT of "Named divergences" because it will no longer be one.

## How to invoke this doctrine

When a design proposal would diverge from OWID:

1. State explicitly: "this is an OWID divergence on `<axis>`."
2. Cite the named yen-gov-specific reason from this doc, or add a new named divergence entry to the table above in the same commit.
3. If the reason is "I think this is nicer," default to OWID. Aesthetics are not a divergence reason — the OWID pattern is the aesthetic.

When an agent debate (Gregor / Fowler / Jony / Hans / Max) is split:

1. Ask: "what does OWID do here?"
2. If OWID has a clear pattern and no named yen-gov divergence applies, that's the answer. Close the debate.
3. If OWID's pattern is ambiguous or doesn't address the case, the agents resolve it on yen-gov's own terms and the resolution becomes either an ADR or a new row in the table above.

## What this doctrine does NOT cover

- **Code-level engineering craft** (refactor catalogue, test tiers, Tidy First). Owned by Fowler / CLAUDE.md.
- **Indian-fiscal-federalism framing** (Finance Commission, GST devolution, scheme attribution). Owned by Hans.
- **Visual design / typography / colour ramps.** Owned by Jony / [docs/architecture/frontend/colours.md](../architecture/frontend/colours.md).
- **Indicator scouting / coverage strategy** (which indicator to ingest next). Owned by Max — though Max already channels OWID's source-vetting discipline.

## See also

- [ADR-0028 — URL scheme](../architecture/frontend/url-grammar.md#adr-0028-url-scheme-place-first-flat-indicator-slug) — first concrete application of this doctrine.
- [ADR-0022 — place-first IA](place-first-ia.md#adr-0022-place-first-ia-with-topic-catalogue) — names the divergence on geography-in-URL.
- [ADR-0047 - schema-version compatibility](../architecture/data/schema-evolution.md#adr-0047-schema-version-compatibility-contract) - schema-evolution policy aligned with OWID-style additive metadata and explicit migrations.
- [schema evolution §Pending OWID-conformance pivot](../architecture/data/schema-evolution.md#pending-owid-conformance-pivot-stop-stamping-schema_version-onto-data-emit-files) — open divergence on `$schema_version` on data emit files; pivot tracked in [TODO/20260612-schema-version-field-refactor-plan.md](../../TODO/20260612-schema-version-field-refactor-plan.md).
- [schema evolution](../architecture/data/schema-evolution.md) - living policy for reader compatibility and no mechanical restamps.
- [citizen-first doctrine](citizen-first.md) — the audience choice that drives the place-first divergence.
- [folded-indicator concept](folded-indicator.md) — names the divergence on Indian publisher vocabulary.

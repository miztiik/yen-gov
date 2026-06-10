# Decision Index

**Last Updated**: 2026-06-11
**Status**: Active redirect contract. Historical `ADR-NNNN` references resolve here; numbers are never reused.

## Why this exists

By 2026-06-03 the repo carried 44 numbered ADR files under `docs/architecture/decisions/`. Per [ADR-0034](../concepts/documentation-discipline.md#adr-0034-documentation-routing-contract)'s own routing rule, the ADR tier retired: each LIVE ADR folded into its subsystem or concept doc as two append-only sections (`## Design rationale` + `## Rejected alternatives`), and each SUPERSEDED-or-REJECTED ADR moved verbatim to `docs/archive/decisions/`. This file is the permanent redirect table that lets any historical `ADR-NNNN` citation resolve to its new home without breaking the link chain.

The receipts (rejected alternatives) move WITH the body; nothing is deleted. The migration's safety net is the `grep-receipts-eq` gate (baseline recorded below). Per CLAUDE.md section 5 "agent memory is derived, not authoritative" - this file is the authoritative routing contract; agent memory self-corrects.

## Anchor convention

LIVE ADRs (37 files): receipt lives inside a subsystem doc under `docs/architecture/<area>/` or a concept doc under `docs/concepts/`. The fold-row (D-DOC3.3..D-DOC3.9) authors the receipt as two sub-sections, each anchored by the ADR's stable slug:

- `### ADR-NNNN: <short title>` under the doc's `## Design rationale` section -> anchor `#adr-NNNN-<short-title-slug>`.
- `### ADR-NNNN rejected alternatives` under the doc's `## Rejected alternatives` section -> anchor `#adr-NNNN-rejected-alternatives`.

The `Target` column below pins the file-level destination and the design-rationale anchor (the rejected-alternatives anchor is mechanical from the same ADR number; consumers grep on the file). Where the fold-row creates a NEW destination doc (e.g. `docs/concepts/url-grammar.md` for D-DOC3.6), the index commits the planned filename; the fold-row that lands the doc honours this filename.

ARCHIVED ADRs (7 files): body moves verbatim under `docs/archive/decisions/NNNN-<slug>.md`; one-line cross-link is appended to the successor's `## Rejected alternatives` section per the trace table at the bottom of this index.

## Migration gate baseline (grep-receipts-eq)

Recorded 2026-06-04, before any fold-row landed, against the then-44 ADR files under `docs/architecture/decisions/` (directory subsequently deleted in D-DOC3.10 closure 2026-06-05; baselines below preserve the pre-fold methodology + counts as historic record):

| Pattern | Count | Notes |
| --- | --- | --- |
| `^## (Rejected alternatives\|Alternatives considered)` (case-sensitive, no end-anchor; matches the strict sub-plan invocation) | **33** | h2 only, exact phrasing prefix; baseline that anchors a strict gate |
| `^#{2,3}\s*(Rejected alternatives\|Alternatives considered)` (case-insensitive; h2 or h3) | **38** | catches h3 (0023, 0043), case variants (0032, 0041, 0042 "Rejected Alternatives"), and extended phrasings ("Alternatives considered (rejected)", "Alternatives considered (and rejected)") |

The load-bearing assertion at every intermediate fold-row PR is that **both numbers stay equal pre- and post-migration** across the union `docs/architecture/ + docs/concepts/ + docs/archive/decisions/`. At D-DOC3.10 closure the originating `docs/architecture/decisions/` directory was deleted; the destination-doc receipts (folded as additive h3 subsections under existing h2s in many cases, per the D-DOC3.6 / 3.7 / 3.8 / 3.5 / 3.4 notes) survived intact. Post-delete state on 2026-06-05: 28 strict h2 / 31 broader h2-or-h3 across the post-delete union. Each fold-row PR cited the running count using the same patterns above to prove no receipt block was lost.

The `grep-receipts-eq` gate assertion on 2026-06-04 asserted 36 -- that number was wrong (filesystem-counted truth supersedes in-flight memory). The strict count is 33 and the broader count is 38; the correction is recorded here.

The strict-pattern invocation as a single line (POSIX):

```
grep -rc --include='*.md' -E '^## (Rejected alternatives|Alternatives considered)' docs/architecture/decisions/ | awk -F: '{s+=$2}END{print s}'
```

The broader-pattern invocation (also POSIX):

```
grep -ric --include='*.md' -E '^#{2,3}\s*(Rejected alternatives|Alternatives considered)' docs/architecture/decisions/ | awk -F: '{s+=$2}END{print s}'
```

After each fold-row PR, the same two invocations run against the new union path set `docs/architecture/ docs/concepts/ docs/archive/decisions/` (excluding `docs/archive/plans/` which is frozen historical) and must return 33 + 38 respectively.

## The index

| ADR | Title | Status | Target |
| --- | --- | --- | --- |
| 0002 | provenance-as-sources-list | superseded-by-0030 | [docs/archive/decisions/0002-provenance-as-sources-list.md](../archive/decisions/0002-provenance-as-sources-list.md) (trace -> [data-provenance.md#adr-0002-rejected-alternatives](../concepts/data-provenance.md#adr-0002-rejected-alternatives))|
| 0003 | no-fetch-cache | accepted | [docs/architecture/backend/core.md#adr-0003-no-fetch-cache](../architecture/backend/core.md#adr-0003-no-fetch-cache)|
| 0014 | sqlite-emitter | superseded-by-0030 | [docs/archive/decisions/0014-sqlite-emitter.md](../archive/decisions/0014-sqlite-emitter.md) (trace -> [canonical-store.md#adr-0014-rejected-alternatives](../architecture/data/canonical-store.md#adr-0014-rejected-alternatives))|
| 0015 | constituency-hierarchy-fields | accepted | [docs/concepts/electoral-hierarchy.md#adr-0015-constituency-hierarchy-fields](../concepts/electoral-hierarchy.md#adr-0015-constituency-hierarchy-fields)|
| 0016-eci | eci-statistical-reports-canonical | accepted | [docs/architecture/backend/sources-eci.md#adr-0016-eci-statistical-reports-canonical](../architecture/backend/sources-eci.md#adr-0016-eci-statistical-reports-canonical)|
| 0016-frontend | frontend-hash-routing | superseded-by-0028 | [docs/archive/decisions/0016-frontend-hash-routing.md](../archive/decisions/0016-frontend-hash-routing.md) (trace -> [url-grammar.md#adr-0016-frontend-rejected-alternatives](../architecture/frontend/url-grammar.md#adr-0016-frontend-rejected-alternatives))|
| 0017-eci | eci-current-year-ingestion | accepted | [docs/architecture/backend/sources-eci.md#adr-0017-eci-current-year-ingestion](../architecture/backend/sources-eci.md#adr-0017-eci-current-year-ingestion)|
| 0017-explore | explore-page-uses-sql-js | superseded-by-0030 | [docs/archive/decisions/0017-explore-page-uses-sql-js.md](../archive/decisions/0017-explore-page-uses-sql-js.md) (trace -> [canonical-store.md#adr-0017-explore-rejected-alternatives](../architecture/data/canonical-store.md#adr-0017-explore-rejected-alternatives))|
| 0018 | wikipedia-district-name-resolution | accepted | [docs/architecture/backend/sources-wikipedia.md#adr-0018-wikipedia-district-name-resolution](../architecture/backend/sources-wikipedia.md#adr-0018-wikipedia-district-name-resolution)|
| 0019 | dataset-topology-and-column-discipline | accepted (amended 2026-05-15) | [docs/architecture/data/canonical-store.md#adr-0019-dataset-topology-and-column-discipline](../architecture/data/canonical-store.md#adr-0019-dataset-topology-and-column-discipline)|
| 0020 | indicator-artifact-as-data-contract | accepted | [docs/architecture/data/indicator-catalogue.md#adr-0020-indicator-artifact-as-data-contract](../architecture/data/indicator-catalogue.md#adr-0020-indicator-artifact-as-data-contract) (NEW doc)|
| 0021 | no-implementation-disclosure-on-public-pages | accepted | [docs/concepts/citizen-first.md#adr-0021-no-implementation-disclosure-on-public-pages](../concepts/citizen-first.md#adr-0021-no-implementation-disclosure-on-public-pages)|
| 0022 | place-first-ia-with-topic-catalogue | accepted | [docs/concepts/place-first-ia.md#adr-0022-place-first-ia-with-topic-catalogue](../concepts/place-first-ia.md#adr-0022-place-first-ia-with-topic-catalogue) (NEW doc)|
| 0023 | election-event-identity-per-place | accepted | [docs/concepts/electoral-hierarchy.md#adr-0023-election-event-identity-per-place](../concepts/electoral-hierarchy.md#adr-0023-election-event-identity-per-place)|
| 0024 | backend-aggregator-for-facetted-indicators | superseded-by-PR-7b | [docs/archive/decisions/0024-backend-aggregator-for-facetted-indicators.md](../archive/decisions/0024-backend-aggregator-for-facetted-indicators.md) (trace -> [indicator-catalogue.md#adr-0024-rejected-alternatives](../architecture/data/indicator-catalogue.md#adr-0024-rejected-alternatives))|
| 0025 | rename-national-to-fiscal-actor-prefixes | accepted | [docs/concepts/indicator-naming.md#adr-0025-rename-national-to-fiscal-actor-prefixes](../concepts/indicator-naming.md#adr-0025-rename-national-to-fiscal-actor-prefixes)|
| 0026 | lift-collection-inventory-out-of-indicator-artifact | accepted | [docs/architecture/data/indicator-catalogue.md#adr-0026-lift-collection-inventory-out-of-indicator-artifact](../architecture/data/indicator-catalogue.md#adr-0026-lift-collection-inventory-out-of-indicator-artifact) (NEW doc)|
| 0027 | cadence-as-separate-field-from-time-grain | accepted | [docs/concepts/indicator-naming.md#adr-0027-cadence-as-separate-field-from-time-grain](../concepts/indicator-naming.md#adr-0027-cadence-as-separate-field-from-time-grain)|
| 0028 | url-scheme-place-first-flat-indicator-slug | accepted (amended by 0037) | [docs/architecture/frontend/url-grammar.md#adr-0028-url-scheme-place-first-flat-indicator-slug](../architecture/frontend/url-grammar.md#adr-0028-url-scheme-place-first-flat-indicator-slug) (NEW doc)|
| 0029 | unmapped-region-chips | superseded-by-D.1.A-retirement | [docs/archive/decisions/0029-unmapped-region-chips.md](../archive/decisions/0029-unmapped-region-chips.md) (trace -> [map.md#adr-0029-rejected-alternatives](../architecture/frontend/map.md#adr-0029-rejected-alternatives))|
| 0030 | canonical-store-duckdb-wasm | accepted | [docs/architecture/data/canonical-store.md#adr-0030-canonical-store-duckdb-wasm](../architecture/data/canonical-store.md#adr-0030-canonical-store-duckdb-wasm)|
| 0031 | boundary-geometry-strategy | accepted (amended 2026-05-25) | [docs/architecture/data/boundaries.md#adr-0031-boundary-geometry-strategy](../architecture/data/boundaries.md#adr-0031-boundary-geometry-strategy)|
| 0032 | sources-citation-ledger | accepted (vintage superseded by 0042) | [docs/concepts/data-provenance.md#adr-0032-sources-citation-ledger](../concepts/data-provenance.md#adr-0032-sources-citation-ledger)|
| 0033 | retire-wikipedia-districts-adapter | accepted | [docs/architecture/backend/sources-wikipedia.md#adr-0033-retire-wikipedia-districts-adapter](../architecture/backend/sources-wikipedia.md#adr-0033-retire-wikipedia-districts-adapter)|
| 0034 | documentation-routing-contract | accepted | [docs/concepts/documentation-discipline.md#adr-0034-documentation-routing-contract](../concepts/documentation-discipline.md#adr-0034-documentation-routing-contract) (NEW doc; CLAUDE.md section 5 cites this index)|
| 0035 | persons-fork-option-b | accepted | [docs/architecture/data/elections-persons.md#adr-0035-persons-fork-option-b](../architecture/data/elections-persons.md#adr-0035-persons-fork-option-b) (NEW doc)|
| 0036 | state-identity-and-slice-registration | accepted | [docs/architecture/data/canonical-store.md#adr-0036-state-identity-and-slice-registration](../architecture/data/canonical-store.md#adr-0036-state-identity-and-slice-registration) (cross-link from [electoral-hierarchy.md](../concepts/electoral-hierarchy.md))|
| 0037 | url-grammar-drop-india-prefix | accepted | [docs/architecture/frontend/url-grammar.md#adr-0037-url-grammar-drop-india-prefix](../architecture/frontend/url-grammar.md#adr-0037-url-grammar-drop-india-prefix) (NEW doc)|
| 0038 | yenask-two-stage-llm-pipeline-rejected | rejected | [docs/archive/decisions/0038-yenask-two-stage-llm-pipeline-rejected.md](../archive/decisions/0038-yenask-two-stage-llm-pipeline-rejected.md) (trace -> [yenask/pipeline.md#adr-0038-rejected-alternatives](../architecture/frontend/yenask/pipeline.md#adr-0038-rejected-alternatives))|
| 0039 | yenask-retrieval-augmented-intent-extraction | accepted (brand-mark partly superseded by 0040) | [docs/architecture/frontend/yenask/pipeline.md#adr-0039-yenask-retrieval-augmented-intent-extraction](../architecture/frontend/yenask/pipeline.md#adr-0039-yenask-retrieval-augmented-intent-extraction) (NEW doc)|
| 0040 | yenask-brand-and-lab-route | accepted | [docs/architecture/frontend/yenask/brand-and-route.md#adr-0040-yenask-brand-and-lab-route](../architecture/frontend/yenask/brand-and-route.md#adr-0040-yenask-brand-and-lab-route) (NEW doc)|
| 0041 | meadow-tier | accepted (meadow tier retired post-B4) | [docs/architecture/data/canonical-store.md#adr-0041-meadow-tier](../architecture/data/canonical-store.md#adr-0041-meadow-tier) (cross-link from existing [meadow-tier.md](../concepts/meadow-tier.md) concept doc) |
| 0042 | sources-schema-v3-vintage-as-period-anchor | accepted | [docs/concepts/data-provenance.md#adr-0042-sources-schema-v3-vintage-as-period-anchor](../concepts/data-provenance.md#adr-0042-sources-schema-v3-vintage-as-period-anchor)|
| 0043 | auto-rollup-at-canonical-write-time | accepted | [docs/architecture/data/canonical-store.md#adr-0043-auto-rollup-at-canonical-write-time](../architecture/data/canonical-store.md#adr-0043-auto-rollup-at-canonical-write-time)|
| 0044 | grain-over-entity | accepted | [docs/concepts/indicator-naming.md#adr-0044-grain-over-entity](../concepts/indicator-naming.md#adr-0044-grain-over-entity)|
| 0045 | grapher-catalogue-split | accepted | [docs/architecture/data/indicator-catalogue.md#adr-0045-grapher-catalogue-split](../architecture/data/indicator-catalogue.md#adr-0045-grapher-catalogue-split) (NEW doc; cross-link from [docs/architecture/frontend/grapher.md](../architecture/frontend/grapher.md) NEW doc)|
| 0046 | pre-flight-ingest-gate-contract | accepted | [docs/architecture/backend/preflight.md#adr-0046-pre-flight-ingest-gate-contract](../architecture/backend/preflight.md#adr-0046-pre-flight-ingest-gate-contract)|
| 0047-schema | schema-version-compatibility-contract | accepted | [docs/architecture/data/schema-evolution.md#adr-0047-schema-version-compatibility-contract](../architecture/data/schema-evolution.md#adr-0047-schema-version-compatibility-contract)|
| 0047-topojson | topojson-as-render-encoding | accepted | [docs/architecture/frontend/topojson-loader.md#adr-0047-topojson-as-render-encoding](../architecture/frontend/topojson-loader.md#adr-0047-topojson-as-render-encoding)|
| 0048 | elections-drill-ia-and-tile-cartogram | accepted | [docs/architecture/frontend/charts/election-views.md#adr-0048-elections-drill-ia-and-tile-cartogram](../architecture/frontend/charts/election-views.md#adr-0048-elections-drill-ia-and-tile-cartogram) (NEW doc under existing charts/ folder)|
| 0049 | canonical-ac-join-key | accepted | [docs/concepts/electoral-hierarchy.md#adr-0049-canonical-ac-join-key](../concepts/electoral-hierarchy.md#adr-0049-canonical-ac-join-key)|
| 0050 | folder-naming-lgd-slug | accepted | [docs/architecture/data/canonical-store.md#adr-0050-folder-naming-lgd-slug](../architecture/data/canonical-store.md#adr-0050-folder-naming-lgd-slug)|
| 0051 | historical-pc-crosswalk-and-delimitation-policy | accepted | [docs/concepts/electoral-hierarchy.md#adr-0051-historical-pc-crosswalk-and-delimitation-policy](../concepts/electoral-hierarchy.md#adr-0051-historical-pc-crosswalk-and-delimitation-policy)|
| 0052 | election-event-in-path-not-query | accepted | [docs/architecture/frontend/url-grammar.md#adr-0052-election-event-in-path-not-query](../architecture/frontend/url-grammar.md#adr-0052-election-event-in-path-not-query) (NEW doc, same as 0028/0037)|

Row count: 44 ADRs (37 live, 7 archived).

## Receipt traces for the 7 archived ADRs

Each archived ADR's body moves verbatim to `docs/archive/decisions/`. A one-line cross-link is appended to the successor doc's `## Rejected alternatives` block, anchored at `#adr-NNNN-rejected-alternatives` (or `#adr-NNNN-<disambiguator>-rejected-alternatives` when the same number has two files):

| ADR | Successor | Trace destination (one-line cross-link in survivor doc) |
| --- | --- | --- |
| 0002 provenance-as-sources-list | 0030 | `docs/concepts/data-provenance.md` `## Rejected alternatives` -> "domain-as-identity (per archived ADR-0002)" |
| 0014 sqlite-emitter | 0030 | `docs/architecture/data/canonical-store.md` `## Rejected alternatives` -> "in-bundle SQLite as canonical store (per archived ADR-0014)" |
| 0016-frontend frontend-hash-routing | 0028 | `docs/architecture/frontend/url-grammar.md` `## Rejected alternatives` -> "hash-routing on the frontend (per archived ADR-0016 frontend-hash-routing); path routing on Pages adopted per ADR-0028" |
| 0017-explore explore-page-uses-sql-js | 0030 | `docs/architecture/data/canonical-store.md` `## Rejected alternatives` -> "sql.js for the explore page (per archived ADR-0017 explore-page-uses-sql-js)" |
| 0024 backend-aggregator-for-facetted-indicators | PR 7b retirement | `docs/architecture/data/indicator-catalogue.md` `## Rejected alternatives` -> "backend Aggregator composer for facetted indicators (per archived ADR-0024)" |
| 0029 unmapped-region-chips | D.1.A retirement | `docs/architecture/frontend/map.md` `## Rejected alternatives` -> "chip-based unmapped-region label (per archived ADR-0029); the surface was retired wholesale 2026-05-30" |
| 0038 yenask-two-stage-llm-pipeline-rejected | 0039 | `docs/architecture/frontend/yenask/pipeline.md` `## Rejected alternatives` -> "two-stage LLM pipeline (per archived ADR-0038)" |

## Forbidden moves

- A new numbered ADR file MUST NOT be authored. New rationale + rejected alternatives go directly into the relevant subsystem or concept doc per [ADR-0034](#adr-0034) routing rule.
- ADR numbers MUST NOT be reused. This index is the permanent reservation list; an `ADR-NNNN` reference always means "the historical ADR with number NNNN" regardless of where the body now lives.
- Receipt blocks (`## Rejected alternatives`) are append-only inside the destination doc. A fold-row MUST NOT delete an existing rejected-alternative entry; it adds the receipt being lifted.
- Cross-references inside ALREADY-ARCHIVED plan-docs under `docs/archive/plans/` are NOT rewritten - they are frozen historical artifacts (per sub-plan scope).

## See also

- Sub-plan: [docs/archive/plans/20260604-d-doc3-adr-retire-subplan.md](../archive/plans/20260604-d-doc3-adr-retire-subplan.md) -- the 10-row execution ledger that consumes this index.
- Routing contract that this index honours: [ADR-0034](../concepts/documentation-discipline.md#adr-0034-documentation-routing-contract).
- Doc class catalogue: [docs/reference/documentation-structure.md](documentation-structure.md) section 7 (the four-class routing standard).

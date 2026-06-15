# Election views - drill IA, TileCartogram, AC/PC grain, filter grammar

**Last Updated**: 2026-06-05

This page is the keep-receipts home for the elections-renderer fence + the generic TileCartogram primitive per [decision-index.md](../../../reference/decision-index.md). It carries the condensed Context + Decision + Consequences for the one live ADR that pinned the elections-drill IA (0048) and the verbatim rejected-alternatives trace. The operational `TileCartogram.svelte` primitive + layout-dataset shape + filter-state plumbing live in the sibling component docs ([chart-shell.md](chart-shell.md), [generic-renderers.md](generic-renderers.md)) and `frontend/src/lib/charts/`; this page carries only the architectural-decision receipts.

> **DOCTRINE NOTE (2026-06-04).** The drill IA, grain-split, TileCartogram fence, and filter URL grammar survive the canonical-store CSV cutover unchanged. Layout datasets (tile-cartogram geometries) are frontend-owned render data per [ADR-0045](../../data/indicator-catalogue.md#adr-0045-grapher-catalogue-split) (lives under `datasets/grapher/`, not canonical election data); the canonical observation rows the cartogram colours come from migrate to long-format CSV under `datasets/data/datapoints/electoral/` (via the canonical CSV migration), but the render contract (grain-agnostic SVG primitive, fed by a layout dataset, election-mount-only in v1) is invariant to the storage format.

## Design rationale

This section folds in the receipt from the originating ADR that pinned the elections-drill IA + generic-cartogram fence + filter URL grammar (`docs/election-views.md#adr-0048-elections-drill-ia-and-tile-cartogram` deleted in D-DOC3.10 closure), per the ADR retirement contract ([decision-index.md](../../../reference/decision-index.md)). The verbatim rejected alternatives live under [Rejected alternatives](#rejected-alternatives).

### ADR-0048: elections-drill-ia-and-tile-cartogram

**Context.** yen-gov ships AC (assembly-constituency) election results today but has no national Parliament (PC / parliamentary-constituency) experience, no equal-seats cartogram, no cross-year change visualisation, and no faceted constituency filtering. The user approved a UK-elections-style experience (reference: the UK `data-analytics` geographic-vs-hex toggle; `indian_mlas` faceted filters) and explicitly authorised breaking the "elections is just one topic on the generic state page" constraint for this work only. Indian election results have a CONSTITUENCY GRAIN - AC for state assembly, PC for Parliament. Constituencies do NOT nest into villages or sub-districts; the honest drill stops at the constituency leaf. This ADR locks the contracts the three execution lanes (docs, backend PC ingest, frontend machinery) build against.

**Decision.** Seven rules:

1. **Drill IA**:

   ```
   /t/elections/:event   (NEW national PC atlas)
      -> /s/:state/elections/:event   (existing state surface; canonical shared URL. `/lab/:state/:event` is a dev-only alias, never the shared link)
          -> ?d=<district>     (a FILTER on the state surface, NOT a route)
              -> /s/:state/ac/:ac   (existing constituency leaf)
   ```

   The place page `/s/:state` remains the spine. There is NO village/sub-district level for election results - the drill terminates at the constituency leaf.

2. **Grain split**: National = PC grain; state = AC grain. UI components are GRAIN-AGNOSTIC: a "unit" is a constituency of either kind. The same `TileCartogram` / choropleth / loader code serves both; the grain is dispatched from the observation row's `entity_kind` (`ac` | `pc`), never from a hardcoded constant. This follows [ADR-0044](../../../concepts/indicator-naming.md#adr-0044-grain-over-entity) (grain rides on the row).

3. **Generic TileCartogram, election-mount-only in v1**: one reusable SVG primitive (`frontend/src/lib/charts/TileCartogram.svelte`) fed by a layout dataset. It is NOT wired to welfare / denominator indicators in v1 - equal-sizing welfare data (where population, area, or budget differ wildly per entity) is misleading (Hans + Max veto). Tile layouts are FRONTEND-OWNED RENDER DATA under `datasets/grapher/` per [ADR-0045](../../data/indicator-catalogue.md#adr-0045-grapher-catalogue-split), NOT canonical election data, and carry their own schema + `source_id` + `derivation_method`.

4. **Toggle**: a segmented control labelled **`Map`** / **`Equal seats`** (never the jargon "choropleth" / "cartogram"). Default is geographic (`Map`) at all levels. The mode persists to the URL as `?view=geo|hex`. The `Equal seats` arm carries the legend line "Each tile = one seat."

5. **Cross-year ship order**: (a) seat-composition bars + per-party swing arrows (default-on; cheapest signal); (b) snapping time-slider on the map/cartogram - snaps to election years only, NO interpolation, NO autoplay; (c) opt-in 2-election capped sankey (top-6 parties + merged "Others"), labelled "Flow (beta)", collapsed by default. Honesty banner: seat deltas, not voter-panel tracking.

6. **Filter URL grammar** (the contract PR-B8 / PR-B9 implement):

   | Param | Values | Default | Scope | Meaning |
   | --- | --- | --- | --- | --- |
   | `party` | csv of party short codes, lower-case (e.g. `bjp,inc`), from the party taxonomy short-code vocabulary (`datasets/taxonomy/parties.json`) | absent = all parties shown, none dimmed | national + state | highlight winners of these parties; dim the rest |
   | `margin` | `all` \| `lt2` \| `gt20` | `all` | national + state | single highlight band on margin = winner_share - runner_up_share (pp); `all` = no band. Non-partition: the 2-20 pp middle has no v1 value |
   | `mode` | `winner` \| `margin` \| `turnout` \| `age` | `winner` | national + state | colour-by dimension. `mode=age` colours by winner-candidate age and depends on a candidate-age measure that may not exist at PC grain in v1; if absent it falls back to `winner` rather than rendering empty |
   | `view` | `geo` \| `hex` | `geo` | national + state | geographic vs equal-seats |
   | `d` | `<district lgd key>` | absent = all districts | state only (ignored on `/t/elections/:event`) | district filter on the state surface (not a route) |

   Filters are MODIFIERS on a fully-populated default view, NEVER preconditions. A bare `/t/elections/2024-ls` renders the complete national map at every param's default (`mode=winner`, `margin=all`, `view=geo`, no `party`, no `d`); params only narrow / recolour it. Composition: params combine with AND across params and OR within a csv (e.g. `party=bjp,inc&margin=lt2` = units won by BJP OR INC, AND in a close band). `party` and `d` narrow the highlighted SET; `mode` and `view` only change RENDERING and never remove units. Fail-soft / versioning: an unknown param key, or an unknown value for a known param, is IGNORED and falls back to that param's default - never an error, never a blank screen. Adding a new `mode`/`margin`/`view` value is additive (minor); removing or renaming one is breaking. If applied filters narrow to zero units, the map still renders all units at base styling with an inline "no constituencies match these filters" note - filters never blank the canvas. Full example: `/t/elections/2024-ls?party=bjp&margin=lt2&mode=margin&view=hex`.

7. **Do-not-build list (v1)**: village / sub-district levels for results; full (>2-election) sankey; a second `/t/elections/country/state/...` URL spine (the place spine `/s/:state` is reused); per-state hand-placed bespoke hex layouts (layouts are generated from centroids + persisted; manual cleanup only where Jony flags overlaps); autoplay / interpolated transitions; demographic cross-tabs beyond "colour by".

**Load-bearing contracts from Lane A (PC ingest).** Two backend decisions ride alongside this ADR and are recorded here because the frontend depends on them: (a) **PC shares the `elections` family + `state=` partition** - PC `ObservationRow`s write into the existing `datasets/elections/state=<key>/election_results.parquet`, discriminated by `entity_id` prefix (`IN-PC-...` vs `IN-<state>-AC-...`) + `indicator_id` (`pc-*` vs `ac-*`). No sibling family, no `grain=` partition dimension (Gregor). The `<state_code>` segment in both PC (`IN-PC-<delim_year>-<state_code>-...`) and AC (`IN-<state_code>-AC-<delim_year>-...`) `entity_id`s MUST draw from the same vocabulary as the `state=<key>` partition key, so PC and AC rows for one state co-locate in the same `datasets/elections/state=<key>/` partition. Segment order differs between the two forms (PC carries `state_code` in position 3, AC in position 1); readers MUST recover state/grain from the `entity_kind` and dedicated state columns, never by positional `entity_id` parsing. `<delim_year>` is the 4-digit delimitation year (e.g. `2008`), never a 2-digit form. The national PC query selects by measure + grain column: `WHERE indicator_id='pc-winner-party-id' AND entity_kind='pc'`. Grain is dispatched from the `entity_kind` column (per ADR-0044), never by parsing `entity_id`; the `IN-PC-%` prefix is an identity convenience, not the dispatch key, so the two cannot drift. PC `entity_id` is `IN-PC-<delim_year>-<state_code>-<pc_no>` (globally unique; ECI `pc_no` is per-state). (b) **`pc-*` indicators are sanctioned (Option B with concept-binding)** - the grain-prefix gate (`^(state|district|national)-`) never matches `ac-`/`pc-`; ADR-0044 preserves those as fact-grain prefixes. Every `pc-*` measure that also exists at AC grain shares ONE `concept_id` (in `datasets/taxonomy/concepts.json`) whose `entity_kinds` lists both `ac` and `pc`, making Option B a strict subset of the OWID-pure end-state. A PC-exclusive measure with no AC analog mints its own concept with `entity_kinds: ["pc"]`.

**Consequences.** The drill IA and URL grammar are versionable contracts; PR-B8 / PR-B9 serialize filter state to URL exactly per section 6, so a shared URL reproduces the screen. `TileCartogram` is reusable but deliberately fenced to election mounts in v1; a future welfare-cartogram decision would need its own ADR + a Hans/Max sign-off on the equal-sizing distortion. Reusing the place spine (`/s/:state`) instead of a second election URL tree keeps one canonical place identity. The bare `/s/:state/ac/:ac` AC-leaf URL shape in section 1 was later superseded by [ADR-0052](../url-grammar.md#adr-0052-election-event-in-path-not-query) (the AC leaf nests UNDER the election event in path); section 1's drill IA is unchanged otherwise.

## Rejected alternatives

This section preserves the rejected-alternatives receipts for the ADR whose rationale is folded above, verbatim and append-only per the ADR retirement contract ([decision-index.md](../../../reference/decision-index.md)). Each subsection is anchored as `#adr-NNNN-rejected-alternatives` for the redirect index.

### ADR-0048 rejected alternatives

ADR-0048's body is structured around POSITIVE decisions + an explicit "Do-not-build list (v1)" rather than a separate `## Alternatives considered` section. The receipts that survive as rejected approaches are the v1 do-not-build items below, preserved verbatim from the originating ADR. Append-only per ADR retirement contract.

- **Village / sub-district levels for results.** Rejected for v1: constituencies do NOT nest into villages or sub-districts; the honest drill stops at the constituency leaf.
- **Full (>2-election) sankey.** Rejected for v1: the opt-in 2-election capped sankey (top-6 parties + merged "Others"), labelled "Flow (beta)", collapsed by default, is the v1 shape. A full N-election sankey is deferred until v1 ships and citizen usage signals demand.
- **A second `/t/elections/country/state/...` URL spine.** Rejected: the place spine `/s/:state` is reused; a second URL tree for elections would fork place identity and force every consumer to know which spine the data lives under.
- **Per-state hand-placed bespoke hex layouts.** Rejected: layouts are generated from centroids + persisted; manual cleanup only where Jony flags overlaps. Hand-placed per-state layouts are unmaintainable at 28 states + 8 UTs scale and drift from authoritative geometry.
- **Autoplay / interpolated transitions.** Rejected: the snapping time-slider snaps to election years only; no interpolation between election years (states do not vote continuously), no autoplay (the citizen drives the timeline, not the chrome).
- **Demographic cross-tabs beyond "colour by".** Rejected for v1: the `mode=winner | margin | turnout | age` colour-by dimension is the v1 demographic surface; full cross-tabs (e.g. "show me women winners in close races") are deferred until v1 ships.

Architectural alternatives also rejected, embedded in section 3 (TileCartogram fence) and section 6 (filter grammar):

- **Wire TileCartogram to welfare / denominator indicators in v1.** Rejected by Hans + Max veto: equal-sizing welfare data (where population, area, or budget differ wildly per entity) is misleading; a future welfare-cartogram decision would need its own ADR + sign-off on the equal-sizing distortion.
- **Treat filter params as preconditions (route at zero matches).** Rejected: filters are MODIFIERS on a fully-populated default view; if applied filters narrow to zero units, the map still renders all units at base styling with an inline note - filters never blank the canvas.
- **Fail loud on unknown filter params.** Rejected: unknown param keys / values are IGNORED and fall back to defaults - never an error, never a blank screen (fail-soft contract). Newer bundle values must not break older deployments.

## Per-state elections landing (`/<state>/elections`)

R2 of [TODO/20260615-state-election-event-page-redesign-plan.md](../../../../TODO/20260615-state-election-event-page-redesign-plan.md) (shipped 2026-06-15 as PR #1066 + R2.1 gap-close PR) extended the place spine with a per-state elections landing route. The grammar from ADR-0048 section 1 grows by ONE node, sandwiched between the place page and the per-event surface: `/<state>` -> overview, **`/<state>/elections` -> per-state landing (NEW)**, `/<state>/elections/<event_id>` -> per-event detail. The bare `/<state>/elections` URL (no trailing slash) was previously a 404; now it renders a breadcrumb, the page header `"{State} elections"`, optional hero cards for the latest assembly + latest parliament event, and two parallel tables (Vidhan Sabha + Lok Sabha) with year-as-link to the per-event page. Component: [frontend/src/routes/StateElectionsLanding.svelte](../../../../frontend/src/routes/StateElectionsLanding.svelte). View-model: re-uses `fetchElectionEvents()` + `listEventsForState(catalogue, state_code, kind)` — no new loader. Route registration in [frontend/src/main.ts](../../../../frontend/src/main.ts) places `/:state/elections` AFTER the 3-segment `/:state/elections/:event` so segment-count ordering preserves the more-specific route's first-match guarantee. Per-event detail pages (`StateElection.svelte`) write a `{event_id, viewed_at_iso, body}` tuple to `localStorage` under the per-state key `"yen-gov:last-event:<state_slug>"` on mount; the landing reads that memory (30-day freshness window) and renders an inline `Last viewed` badge next to the matching year-link. All localStorage I/O is funnelled through one helper module, [frontend/src/lib/elections/last-event-memory.ts](../../../../frontend/src/lib/elections/last-event-memory.ts), so the key contract and the expiry rule live in exactly one place. No telemetry, no server round-trip (Holy Law #1).

## See also

- [docs/architecture/frontend/charts/chart-shell.md](chart-shell.md) - the shared chart shell that hosts the TileCartogram primitive.
- [docs/architecture/frontend/charts/generic-renderers.md](generic-renderers.md) - grain-agnostic renderer contracts the cartogram + choropleth share.
- [docs/architecture/frontend/url-grammar.md](../url-grammar.md) - the URL grammar that the elections-drill IA implements at the route layer; specifically [ADR-0052](../url-grammar.md#adr-0052-election-event-in-path-not-query) which supersedes the AC-leaf URL shape in section 1.
- [docs/architecture/data/elections-indicators.md](../../data/elections-indicators.md) - AC + PC indicator catalogue (the `pc-*` measures and the shared-concept rule).
- [docs/concepts/electoral-hierarchy.md](../../../concepts/electoral-hierarchy.md) - the AC/PC nesting model the drill IA is built on; specifically [ADR-0049](../../../concepts/electoral-hierarchy.md#adr-0049-canonical-ac-join-key) (canonical AC join key) + [ADR-0051](../../../concepts/electoral-hierarchy.md#adr-0051-historical-pc-crosswalk-and-delimitation-policy) (historical PC crosswalk).
- [docs/concepts/indicator-naming.md](../../../concepts/indicator-naming.md) - the grain-over-entity rule the renderers dispatch from ([ADR-0044](../../../concepts/indicator-naming.md#adr-0044-grain-over-entity)).
- [docs/concepts/schema-is-the-design-system.md](../../../concepts/schema-is-the-design-system.md) - the renderer doctrine the elections renderer fence sits inside.
- [decision-index.md](../../../reference/decision-index.md) - the redirect index pinning every ADR to its new doc anchor.

# ADR-0028: URL scheme — place-first cascade, flat indicator slug, path routing

**Last Updated**: 2026-05-17
**Status**: accepted
**Supersedes**: [ADR-0016 (hash routing)](0016-frontend-hash-routing.md) — on routing-mode only. ADR-0016's reasoning (YAGNI for a 4-route SPA) was correct at the time; the present scale (~50 routes growing to ~5,400 once indicator-in-path lands) and the shareability contract make path routing the load-bearing choice.

## Context

Two design pressures converged:

1. **Country-entity routes** (TODO/20260517-iced-bulk-ingest-and-parity-oracle.md Phase 3b) were about to land as `/c/<country>/...`, forcing a decision on whether to mirror the existing `/s/<state>/...` shape or rewrite to a uniform marker-prefixed cascade `/c/<country>/s/<state>/[d/<district>|ac/<seat>]/i/<id>`.
2. **User direction** (verbatim, 2026-05-17): "we are over complicating. Country can directly be India... slash India slash delhi and then the constituency under that... I would prefer not to have the number prefix... I like Max's opinion because the scale at OWID works."

Five voices were consulted (Gregor architect, Fowler engineer, Jony UI/UX, Hans governance, Max indicator-scout). The synthesis is recorded in §Five-voice digest below.

The user also explicitly directed: codify "align with OWID standards" as a fallback doctrine so future conflicts on URL / indicator-id / granularity / discoverability resolve to "what does Our World in Data do?" rather than re-debate. That doctrine lives in [docs/concepts/owid-alignment.md](../../concepts/owid-alignment.md); this ADR is its first concrete application.

## Decision

**Scheme:** place-first cascade, marker-less, with the indicator as the optional last segment of any cascade. Slug is flat (one path segment per indicator). Path routing on GitHub Pages via the standard `404.html → index.html` SPA shim. ADR-0016 is superseded for the routing-mode question.

### Route grammar

| Surface | URL |
|---|---|
| Country home | `/india` |
| State | `/india/tamil-nadu` |
| District | `/india/tamil-nadu/chennai` (when a district page exists; deferred until a renderer ships) |
| AC | `/india/tamil-nadu/mylapore` |
| Indicator @ national | `/india/installed-capacity` |
| Indicator @ state | `/india/tamil-nadu/installed-capacity` |
| Indicator @ AC | `/india/tamil-nadu/mylapore/installed-capacity` |

### Resolution contract

The router walks the path from `/india` left-to-right, consulting the geography registry at each segment. When the next segment is NOT a known sub-geography of the current node, it consults the indicator-slug registry. If the segment is in neither, the result is a real 404.

- Geography registries: `datasets/reference/in/states.json`, `datasets/reference/in/states/<state>/districts.json`, ECI per-state constituency lists.
- Indicator-slug registry: derived field on the existing `datasets/reference/in/indicators-completeness.json`. Maps `url_slug` → canonical indicator id (`installed-capacity` → `power/installed-capacity`).
- One Tier-A contract test (CLAUDE.md §15) enforces: `indicator_slugs ⊥ {state_slugs ∪ district_slugs ∪ ac_slugs ∪ RESERVED_SEGMENTS}` where `RESERVED_SEGMENTS = ["india", "indicator", "compare", "explore", "about", "disclaimer", "data-completeness"]`. The test reads the registries and asserts the set intersection is empty.

### AC slug shape

Name-only, no number prefix (the prior `167-mylapore` form is dropped). The ECI code (`S22-167`) remains the canonical identifier in data; the URL slug is the AC name slugified. If two ACs in the same state ever share a name (rare), the second emits as `<name>-2`, enforced by the emit-time slug-uniqueness check. ECI guarantees per-state name uniqueness in current rolls; the fallback exists only for delimitation edge cases.

### Indicator slug shape

Flat single segment, not the producer-side slash hierarchy. Producer keeps `<topic>/<leaf>` IDs (e.g. `power/installed-capacity`) for storage and the indicator catalogue. The URL slug is a registry-backed projection (`installed-capacity`) resolved at route time. Per Max's OWID precedent: OWID at ~10,000 indicators uses flat slugs (`/grapher/co2-emissions-per-capita`, not `/environment/emissions/...`) precisely because retaxonomising a topic tree is destructive to URL stability, and URL stability is a citizen-trust contract.

Topic discovery lives in the IA layer (topic hubs, faceted search, breadcrumbs), not the URL spine.

### Vintage in URL

No. Per Hans: putting vintage in the path freezes a shared link to a vintage the sharer didn't consciously choose and invites silent cross-vintage comparisons across methodology breaks. Latest by default; `?as_of=<vintage>` permitted only for citation/replication, never as the canonical share link.

### Hash routing

Rejected. Path routing on GitHub Pages via the `404.html → index.html` shim is the OWID-standard pattern and is widely-solved (~5 lines). Hash routing breaks link unfurls (Telegram/WhatsApp/Slack OG scrapers see only `/`), is inconsistently indexed by search engines, and reads as "broken" to citizens copying URLs. ADR-0016's "perpetual footgun" framing of the shim was wrong at present scale.

### Migration of existing routes

All existing `/s/<state>/...` and hash-routed URLs get rewritten. The strangler-fig component issues a client-side redirect (`replaceState`) on legacy URL match for one release cycle, then is deleted. External bookmarks and search-engine index entries are real consumers — the 20-line redirect is cheaper than link rot.

## Five-voice digest

Full transcripts in TODO/20260517-iced-bulk-ingest-and-parity-oracle.md handoff archive. Convergence and dissent:

- **Agreed (all five):** path routing not hash; no `/topic/<topic>/<indicator>` middle segment; no vintage in URL; geography cascade marker-less.
- **Gregor (architect):** preferred a single `/i/` marker mid-cascade for content-based-router honesty. Dissolved by Max's flat slug — when the indicator is always the last segment, position disambiguates without a marker.
- **Fowler (engineer):** preferred `/i/` marker on engineering-cost grounds (one collision class vs many). Dissolved by the same flat-slug move — collision class collapses to one Tier-A contract test against three registries (states, districts, ACs).
- **Jony (UI/UX):** marker-less, paths-not-hashes, flatten the indicator id, preserve cascade. Read-aloud test: "India, Tamil Nadu, installed capacity" — three nouns, no scaffolding.
- **Hans (governance):** marker-less enables one-segment state-swap (`tamil-nadu` → `kerala`) for journalist comparison flows. No vintage in URL.
- **Max (indicator scout, swing vote):** OWID at 10× our target scale uses flat slugs. Topic prefix in URL is fragile under indicator re-homing. Producer-side `<topic>/<leaf>` ID is namespace, not taxonomy; flat URL slug is the citizen-trust contract.

## Alternatives considered

1. **Original `/c/<country>/s/<state>/[d|ac]/<seat>/i/<id>` cascade** (TODO §9 row 3 as originally written). Rejected by user as "over complicating"; markers don't earn their place when slug shapes already disambiguate.
2. **`?i=<indicator>` query-string projection.** Rejected by user explicitly — indicator must live in the path.
3. **`/i/<indicator-id>` reserved-marker scheme** (Gregor + Fowler round 2). Dissolved by flat-slug move; also not OWID-aligned (OWID never uses a positional mid-cascade marker).
4. **Hash routing per ADR-0016.** Rejected — OWID-divergence on the most-visible surface; Jony's read-aloud test fails ("hash slash India"); link unfurl broken.
5. **AC number prefix `167-mylapore`.** Rejected by user — citizen does not navigate by ECI number.
6. **Preserve indicator slash hierarchy in path** (`/india/tamil-nadu/power/installed-capacity`). Rejected — Max's OWID precedent: topic re-homing breaks URL stability; flat slug is the durability bet.

## Consequences

**Good**
- URL is OWID-aligned where it matters (flat indicator slug, path routing, URL stability over taxonomy purity).
- One-segment state-swap supports journalist comparison flows.
- Indicator slug is opaque to topic re-homing (rename topic without breaking citizen URLs).
- Read-aloud test passes for every URL in the grammar.
- Collision detection is one Tier-A contract test reading three registries.

**Bad**
- 404.html shim is now mandatory on GitHub Pages. Operational cost: ~5 lines, one-time.
- Producer-side indicator id (`power/installed-capacity`) ≠ URL slug (`installed-capacity`). Registry lookup is load-bearing at route time and at emit time.
- Indicator slugs must be globally unique. If two topics ever want `installed-capacity`, one renames. Emit-time test catches this.
- All existing URLs change. One-release redirect window covers bookmarks and search-engine index entries.

## Implementation gate

This ADR locks the scheme. Implementation lives in [TODO/20260517-iced-bulk-ingest-and-parity-oracle.md](../../../TODO/20260517-iced-bulk-ingest-and-parity-oracle.md) Phase 3 (amended) and follows the Tidy First commit sequence Fowler specified (paths.ts helper extracted before any route flip; strangler-fig redirect for `/s/<state>*`; contract test green before commits land).

## See also

- [ADR-0016](0016-frontend-hash-routing.md) — superseded on routing-mode.
- [ADR-0022](0022-place-first-ia-with-topic-catalogue.md) — place-first IA doctrine this ADR implements at the URL layer.
- [docs/concepts/owid-alignment.md](../../concepts/owid-alignment.md) — fallback doctrine this ADR exemplifies.
- [docs/architecture/frontend/routing.md](../frontend/routing.md) — the route grammar + collision contract in operational form.

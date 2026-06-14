# URL grammar - ADR receipts (place-first cascade + drop `/india/` prefix + rejected hash-routing)

**Last Updated**: 2026-06-12

This page is the keep-receipts home for the project's URL grammar decisions per [decision-index.md](../../reference/decision-index.md). It carries the condensed Context + Decision + Consequences for the two live ADRs that lock the grammar (0028 + 0037) and the verbatim rejected-alternatives traces for both the live and the archived ADRs (0028, 0037, and archived 0016-frontend-hash-routing). The operational form of the route resolver lives in the sibling subsystem doc [routing.md](routing.md); this page carries only the architectural-decision receipts.

> **DOCTRINE NOTE (2026-06-04).** The URL grammar (place-first cascade, flat indicator slug, path routing on Pages, no-vintage-in-URL, 5-way namespace disjointness, full-name state slug, entity-type page chrome) survives the canonical-store CSV cutover unchanged. URLs are a citizen contract and a frontend concern; the underlying storage format does not reach them. What MIGRATES is the read seam (`read_csv(columns=...)` over long-format CSV under `datasets/data/` rather than over the retiring Parquet tree per plan chunks F1 / X1a); the URL grammar's load-bearing invariants (OWID-alignment, Wikipedia-alignment on slug-as-entity, read-aloud test, one-segment state-swap) are invariant to the storage format.

## Design rationale

This section folds in the receipts from the originating ADRs that pinned the URL grammar for this project, per the ADR retirement contract ([decision-index.md](../../reference/decision-index.md)). The verbatim rejected alternatives live under [Rejected alternatives](#rejected-alternatives). The archived [ADR-0016 (frontend-hash-routing)](../../archive/decisions/0016-frontend-hash-routing.md) trace also lives in that section per [decision-index.md](../../reference/decision-index.md).

### ADR-0028: url-scheme-place-first-flat-indicator-slug

**Context.** Two design pressures converged. (1) Country-entity routes were about to land as `/c/<country>/...`, forcing a decision on whether to mirror the existing `/s/<state>/...` shape or rewrite to a uniform marker-prefixed cascade `/c/<country>/s/<state>/[d/<district>|ac/<seat>]/i/<id>`. (2) User direction (verbatim, 2026-05-17): "we are over complicating. Country can directly be India... slash India slash delhi and then the constituency under that... I would prefer not to have the number prefix... I like Max's opinion because the scale at OWID works." Five voices were consulted (Gregor architect, Fowler engineer, Jony UI/UX, Hans governance, Max indicator-scout). The user also explicitly directed: codify "align with OWID standards" as a fallback doctrine so future conflicts on URL / indicator-id / granularity / discoverability resolve to "what does Our World in Data do?" rather than re-debate. That doctrine lives in [owid-alignment.md](../../concepts/owid-alignment.md); ADR-0028 is its first concrete application.

**Decision.** Place-first cascade, marker-less, with the indicator as the optional last segment of any cascade. Slug is flat (one path segment per indicator). Path routing on GitHub Pages via the standard `404.html -> index.html` SPA shim. ADR-0016 is superseded for the routing-mode question.

**Route grammar (as originally drafted, later amended by ADR-0037 to drop the `/india/` prefix).**

| Surface | URL (ADR-0028 draft) |
|---|---|
| Country home | `/india` |
| State | `/india/tamil-nadu` |
| District | `/india/tamil-nadu/chennai` |
| AC | `/india/tamil-nadu/mylapore` |
| Indicator @ national | `/india/installed-capacity` |
| Indicator @ state | `/india/tamil-nadu/installed-capacity` |
| Indicator @ AC | `/india/tamil-nadu/mylapore/installed-capacity` |

The final shipped grammar is recorded under [ADR-0037 below](#adr-0037-url-grammar-drop-india-prefix); the operational form sits in [routing.md](routing.md).

**Resolution contract.** The router walks the path from `/india` left-to-right, consulting the geography registry at each segment. When the next segment is NOT a known sub-geography of the current node, it consults the indicator-slug registry. If the segment is in neither, the result is a real 404. Geography registries: `datasets/taxonomy/entities.json` (filter `entity_type IN ('state','ut') AND entity_valid_to IS NULL` for the state list; `entity_type='district'` for the district list), ECI per-state constituency lists. Indicator-slug registry: derived field on the existing `datasets/_ops/indicators-completeness.json` (G8 2026-06-08: was `datasets/reference/in/indicators-completeness.json`) - maps `url_slug` -> canonical indicator id (e.g. `installed-capacity` -> `power/installed-capacity`). One Tier-A contract test (CLAUDE.md section 15) enforces: `indicator_slugs` are disjoint from the union of `{state_slugs, district_slugs, ac_slugs, RESERVED_SEGMENTS}` where `RESERVED_SEGMENTS = ["india", "indicator", "compare", "explore", "about", "disclaimer", "data-completeness"]`. The test reads the registries and asserts the set intersection is empty.

**AC slug shape.** Name-only, no number prefix (the prior `167-mylapore` form is dropped). The ECI code (`S22-167`) remains the canonical identifier in data; the URL slug is the AC name slugified. If two ACs in the same state ever share a name (rare), the second emits as `<name>-2`, enforced by the emit-time slug-uniqueness check. ECI guarantees per-state name uniqueness in current rolls; the fallback exists only for delimitation edge cases.

**Indicator slug shape.** Flat single segment, not the producer-side slash hierarchy. Producer keeps `<topic>/<leaf>` IDs (e.g. `power/installed-capacity`) for storage and the indicator catalogue. The URL slug is a registry-backed projection (`installed-capacity`) resolved at route time. Per Max's OWID precedent: OWID at ~10,000 indicators uses flat slugs (`/grapher/co2-emissions-per-capita`, not `/environment/emissions/...`) precisely because retaxonomising a topic tree is destructive to URL stability, and URL stability is a citizen-trust contract. Topic discovery lives in the IA layer (topic hubs, faceted search, breadcrumbs), not the URL spine.

**Vintage in URL.** No. Per Hans: putting vintage in the path freezes a shared link to a vintage the sharer didn't consciously choose and invites silent cross-vintage comparisons across methodology breaks. Latest by default; `?as_of=<vintage>` permitted only for citation/replication, never as the canonical share link.

**Hash routing.** Rejected. Path routing on GitHub Pages via the `404.html -> index.html` shim is the OWID-standard pattern and is widely-solved (~5 lines). Hash routing breaks link unfurls (Telegram/WhatsApp/Slack OG scrapers see only `/`), is inconsistently indexed by search engines, and reads as "broken" to citizens copying URLs. ADR-0016's "perpetual footgun" framing of the shim was wrong at present scale (~50 routes growing to ~5,400 once indicator-in-path lands).

**Migration of existing routes.** All existing `/s/<state>/...` and hash-routed URLs get rewritten. The strangler-fig component issues a client-side redirect (`replaceState`) on legacy URL match for one release cycle, then is deleted. External bookmarks and search-engine index entries are real consumers - the 20-line redirect is cheaper than link rot.

**Five-voice digest (convergence and dissent).** Agreed (all five): path routing not hash; no `/topic/<topic>/<indicator>` middle segment; no vintage in URL; geography cascade marker-less. Gregor (architect): preferred a single `/i/` marker mid-cascade for content-based-router honesty - dissolved by Max's flat slug (when the indicator is always the last segment, position disambiguates without a marker). Fowler (engineer): preferred `/i/` marker on engineering-cost grounds (one collision class vs many) - dissolved by the same flat-slug move (collision class collapses to one Tier-A contract test against three registries). Jony (UI/UX): marker-less, paths-not-hashes, flatten the indicator id, preserve cascade. Read-aloud test: "India, Tamil Nadu, installed capacity" - three nouns, no scaffolding. Hans (governance): marker-less enables one-segment state-swap (`tamil-nadu` -> `kerala`) for journalist comparison flows. No vintage in URL. Max (indicator scout, swing vote): OWID at 10x our target scale uses flat slugs. Topic prefix in URL is fragile under indicator re-homing. Producer-side `<topic>/<leaf>` ID is namespace, not taxonomy; flat URL slug is the citizen-trust contract.

**Consequences.** URL is OWID-aligned where it matters (flat indicator slug, path routing, URL stability over taxonomy purity). One-segment state-swap supports journalist comparison flows. Indicator slug is opaque to topic re-homing (rename topic without breaking citizen URLs). Read-aloud test passes for every URL in the grammar. Collision detection is one Tier-A contract test reading three registries. Negatives: 404.html shim is now mandatory on GitHub Pages (operational cost: ~5 lines, one-time); producer-side indicator id (`power/installed-capacity`) does not equal URL slug (`installed-capacity`), so registry lookup is load-bearing at route time and at emit time; indicator slugs must be globally unique - if two topics ever want `installed-capacity`, one renames (emit-time test catches this); all existing URLs change, one-release redirect window covers bookmarks and search-engine index entries.

### ADR-0037: url-grammar-drop-india-prefix

**Context.** ADR-0028 (2026-05-17) locked `/india/<state>/<ac>/<indicator>` as the canonical URL grammar after the five-voice debate above. The decision was correct at the time and was endorsed by the user verbatim. In practice, ADR-0028 was never implemented: the codebase shipped `/s/<state>/...` instead (the legacy `RedirectLegacyUrl.svelte` strangler-fig target became the live grammar). PR #172 (2026-05-25) audited and locked the shipped `/s/<state>/...` shape into a 42-test contract - codifying drift without resolving it. On 2026-05-25 the user re-opened the question: "Having nicer URLs is important. In fact I thought it would be just an estate slug name, not even the slash-yes-slash-state. So can you have a conversation debate with all the agents together not independently and then come up to conclusion plan of how this thing can be tracked and updated. So we put this to rest one way or the other." ADR-0037 records the resolution.

**Decision.** Drop the `/india/` segment from ADR-0028's grammar. The state slug sits at the URL root. Everything else about ADR-0028 stands.

**Final route grammar (as shipped; the binding citizen contract).**

| Surface | URL |
|---|---|
| Country home | `/` |
| State hub | `/tamil-nadu` |
| AC | `/tamil-nadu/mylapore` (pure name, no `167-` prefix per ADR-0028 AC-slug) |
| District (when renderer ships) | `/tamil-nadu/chennai` |
| Indicator @ national | `/installed-capacity` |
| Indicator @ state | `/tamil-nadu/installed-capacity` |
| Indicator @ AC | `/tamil-nadu/mylapore/installed-capacity` |
| Topic index | `/t` |
| Topic landing | `/t/energy` |
| Per-state topic | `/tamil-nadu/t/energy` |
| Parties index (ADR-0053) | `/parties` |
| Per-party detail (ADR-0053) | `/parties/<slug>` |
| State explore | `/tamil-nadu/explore` |
| Election lab | `/lab/<state>/<event>` (existing surface; not relocated) |
| Election compare | `/compare/<state>/<event>` (existing surface; not relocated) |
| Cross-state indicator compare | `/installed-capacity` with compare-mode tab (Phase 3+) |
| Chrome | `/about`, `/settings`, `/disclaimer`, `/data-completeness`, `/compare` |

**Reserved positional tokens.** `RESERVED = ["t", "compare", "about", "settings", "disclaimer", "data-completeness", "lab", "dev", "ac", "parties", "i", "explore", "d"]`. No state slug, topic slug, indicator slug, AC slug, or party slug may equal any reserved token. The current reservations cover: `ac`, `explore` = sub-namespace markers; `i` = pre-reserved fallback for the future indicator-marker retrofit; `dev` = the existing dev-only Vite alias; `parties` (plural) = top-level parties index + per-party detail (ADR-0053, supersedes the legacy `party` singular state-scoped reservation); `d` = Deferral 1 future escape-hatch per Jony rule #3.

**Strengthened collision invariant.** ADR-0028's contract was `indicator_slugs` disjoint from the union of `{state_slugs, district_slugs, ac_slugs, RESERVED_SEGMENTS}`. This ADR strengthens it to 5-way pairwise disjointness: the set `{urlIndicatorSlugs, stateSlugs, topicSlugs, acSlugsAcrossAllStates, RESERVED}` is pairwise disjoint. ADR-0053 (2026-06-12) extends this to 6-way by adding `partySlugs` (derived from `parties.csv` via `partyIdToSlug`); each new registry is internally unique AND disjoint from each of the five earlier registries. `topicSlugs` was implicit in ADR-0028 (topics lived under `/india/<state>` so couldn't collide); without the `/india/` prefix topics need explicit guarding. `acSlugsAcrossAllStates` is the largest namespace (~4,123 names) and was missing from the disjointness rule as drafted; AC names include common nouns (`central`, `north`, `south`, `kalyan`) that will collide with future indicator slugs.

**Full-name state slug invariant (new).** Every state slug MUST be the slugified full English `display_name`. `/uttar-pradesh` not `/up`. `/madhya-pradesh` not `/mp`. Two precedents converge on this: Wikipedia (`/wiki/Uttar_Pradesh`) and data.gov.in (`/uttar-pradesh`) are the two URL surfaces a citizen has actually been trained on; ECI's `S24` and MoSPI's `UP` are URLs the citizen never reads. All 36 current state slugs derived from `datasets/taxonomy/entities.json` already meet this invariant; the test is a regression guard.

**Page chrome must carry entity-type framing.** The URL `/<state>` reads as a place-fact (Wikipedia-trained mental model). For constitutional honesty (Delhi is NCT-UT not state; J&K became UT in 2019; Chandigarh + Lakshadweep + Ladakh are UTs without legislature), the state-hub page MUST render an `entity_type` badge (state | UT) under the H1 with the legislative-scope note where applicable, per [ADR-0022 place-first-ia constitutional-honesty rule](../../concepts/place-first-ia.md#adr-0022-place-first-ia-with-topic-catalogue). The URL alone cannot carry this; the page chrome closes it.

**Missing-scope behaviour.** When a citizen visits `/tamil-nadu/<indicator>` for an indicator that exists in the catalogue but has no state-scope rows: render a stub with a one-click deep link to the nearest scope where the indicator is published. Never silent-redirect. Never 404. OWID precedent: `/grapher/<slug>?country=ATA` renders chart frame with "No data for this entity" and the country-picker visible. Wikipedia precedent: redlinks. The stub names the missing thing honestly: "installed-capacity (Tamil Nadu) - not published at state scope. See national: /installed-capacity."

**Cross-state indicator-compare surface.** Lives on the indicator page itself, not at `/compare/<indicator>`. OWID precedent: `/grapher/co2-emissions-per-capita` IS the compare surface - the country-picker is a control on the chart, not a separate URL. The existing election-compare surface at `/compare/<state>/<event>` is a different beast (compares one event outcome across many states) and stays. The cross-state indicator-compare lands in Phase 3+ as a compare-mode tab on the indicator page.

**Three-voice digest (Jony -> Hans -> Max, each voice seeing the previous binding output).** Jony (UI/UX, section 0a authority on URL grammar): chose Grammar A. Read-aloud test: "Tamil Nadu, Mylapore, installed capacity" - three nouns, zero scaffolding. ADR-0028's `/india/` was scaffolding for never-built country-multi-tenancy on a `.in` domain. Self-objection on link-rot blast radius was deemed acceptable: yen-gov has approximately zero external citations today; cost of change grows monotonically with every shared link, so do it now. Hans (governance): ratified A. Added full-name slug invariant (Wikipedia + data.gov.in are the trained precedents; ECI codes + MoSPI abbreviations are negative precedents). Added entity-type badge constraint on page chrome. WhatsApp-forward citizen test: URL names what the page IS, not how the site is organised. Methodology-break survival (Telangana from AP, 2014) is mildly better under A because URL carries the semantic mismatch. Max (indicator scout, OWID precedent): ratified A with one amendment - strengthen the collision invariant to include `acSlugs` (largest namespace, was missing). Missing-scope = stub-not-redirect-not-404 per OWID precedent. Cross-state compare collapses into indicator page per OWID precedent. 10k-indicator scaling estimate: collision-safe today but fragile at OWID scale; threshold for the `/i/<slug>` reserved-marker retrofit is empirical, estimated `N = 800 to 2000` indicator slugs. Do NOT pre-ship the marker; ship the Tier-A disjointness test that signals when retrofit is due.

**Migration (four-phase strangler-fig).** Phase 1 (shipped PR #173): create `links.ts` with Grammar A builders + three Tier-A tests (links shape, 3-way namespace disjointness, full-name state-slug invariant). Zero call-site migration. PR #172's 42-test contract stays green. The `paths.ts` module name is already taken by the runtime `DATA_BASE` prefix helper (unrelated concern); the new route-URL builders live in `links.ts` so the two responsibilities stay separated. **Phase 2 (PR #867, 2026-06-09)**: Grammar A routes added to `main.ts` alongside `/s/*`. `RedirectLegacyUrl.svelte` mounted on `/s/*` and rewrites every legacy bookmark to Grammar A via `history.replaceState`. Router compile extended to support trailing-wildcard patterns. **Phase 3 (PR #868, 2026-06-10)**: caller-migration sweep — every `url.X()` call-site in `frontend/src/**` flipped to `link.X()` (50 files, 613/-240). AC slug shape change shipped here (`167-mylapore` → `mylapore` via the new `link.ac`/`link.acByNo`). AC namespace (~4,123 names) joined the disjointness contract (4-way; 5-way deferred until `url_slug` lands on `taxonomy/indicators.parquet`). Grammar A `/:state` catch-all 404-gates unknown slugs via `states.isLoaded`. **Phase 4 (PR #869, 2026-06-10)**: `url.ts` Grammar B builders + PR #172's 42-test contract DELETED. `url.ts` retains only the three utility primitives (`withBase`, `stripBase`, `navigate`). `RedirectLegacyUrl.svelte` stays mounted on `/s/*` for one release cycle. **Phase 4b (PR #871, 2026-06-10)**: `RedirectLegacyUrl.svelte` + `/s/*` route entry + `redirect-legacy-url.ts` pure helper DELETED. `s` dropped from `RESERVED_PATH_TOKENS`. Legacy bookmarks fall through to NotFound. The 4-phase strangler-fig is COMPLETE.

**Consequences.** URL is OWID-aligned on the load-bearing dimension (flat indicator slug, place-first cascade, path routing) AND Wikipedia-aligned on the slug-as-entity dimension (the URL names what the page IS). One-segment state-swap (`/tamil-nadu/<indicator>` -> `/kerala/<indicator>`) survives. Read-aloud test passes for every URL in the grammar. Entity-rename/split survival is mildly better than the shipped Grammar B because URL is human-debuggable. Collision detection is one Tier-A contract test reading four registries; failure mode is "rename the colliding slug, never add an exception." Negatives: all shipped `/s/<state>/*` URLs change - strangler-fig redirect (Phase 3) covers one release cycle then is deleted in Phase 4b; external citations created during Phase 2/3 window risk link-rot when the redirect retires. PR #172's 42-test contract on the `/s/<state>` shape becomes Phase 4 deletion target. AC slug shape change (`167-mylapore` -> `mylapore`) requires resolver to look up AC by name not number. Per-state topic URL shape (`/<state>/t/<topic>` vs alternatives) is a deferred user-gate question.

### ADR-0052: election-event-in-path-not-query

**Context.** The constituency drill-down page was addressable two ways for the same resource: `/s/<state>/ac/<n-slug>?event=<event>` (event in the QUERY STRING) and `/s/<state>/elections/<event>` (the state election overview, with event in the PATH). So the election event was sometimes a path segment (state overview) and sometimes a query parameter (constituency page). Two URL grammars for one logical thing (an election surface) is more to maintain and reason about, and it blurs the line between "which resource am I looking at" and "how am I looking at it". User direction: "I don't see a reason for having two url patterns for the same data, it makes it harder to maintain two surfaces." This ADR supersedes the AC-leaf URL shape in [ADR-0048](charts/election-views.md#adr-0048-elections-drill-ia-and-tile-cartogram) section 1 (the bare `/s/:state/ac/:ac` leaf with `?event=` is retired as a canonical resource).

**Decision.** Four rules: (1) **Path encodes resource identity; query encodes view-state only.** Path segments encode resource identity (state, election event, constituency). The query string encodes view-state only - filters, colour mode, anything reversible that does not change WHICH resource you are looking at. For elections the event IS identity, never view-state, so it is always a path segment and never a query parameter. (2) **URL grammar is hierarchical by zoom depth, not flat by surface.** The election event is part of the resource identity, so it lives in the path on every election surface:

```
/s/<state>/elections/<event>             state election overview
/s/<state>/elections/<event>/ac/<n-slug> single-constituency drill-down, nested beneath
```

A constituency is NEVER addressable outside an election context. (3) **Bare `/s/<state>/ac/<n-slug>` is a convenience entry, not a canonical resource** - it carries no election in its path, so it is not identity-complete. The constituency page resolves the state's default event and `replaceState`-redirects to the nested canonical form. It is a 302-equivalent (client-side, since the app is a static SPA on GitHub Pages with no server to issue a real 302). (4) **Legacy `?event=` is honoured for one release** - a pre-ADR-0052 bookmark of the form `/s/<state>/ac/<n-slug>?event=<event>` is read by the same redirect path: the query event is resolved and the visitor is `replaceState`-redirected to the nested path form. This keeps existing shared links working through one release; the query form is not emitted by any builder.

**Consequences.** `frontend/src/lib/url.ts`: `ac()` / `acByNo()` emit the nested path when an event is supplied, and the bare `/ac/` form (redirect target) when it is not. The event is never emitted as a query parameter. `frontend/src/main.ts`: canonical route `/s/:state/elections/:event/ac/:ac` -> `Constituency`; the bare `/s/:state/ac/:ac` route is retained only as the redirect entry. `frontend/src/routes/Constituency.svelte`: reads the event from `params.event` (path); falls back to a legacy `?event=` query, then the state default; redirects the bare form to the nested canonical URL. One URL grammar for elections: event in the path everywhere. No second surface to maintain.

### ADR-0053: party-rendering-and-per-party-pages

**Context.** Per-party pages had been state-scoped at `/<state>/party/<slug>` since Phase 1 (slug = `<short>-<eci_code_lower>`, e.g. `/tamil-nadu/party/dmk-5`). Two design pressures broke this. (1) The state scoping was inherited from when "party page" meant "this party's totals in this state's most recent election" — a SLICE, not the entity. A citizen looking up "INC" almost always wants the all-India INC, not "INC in <state>"; a citizen looking up "JD(U)" wants the party-as-actor, not a forced choice between Bihar / Arunachal / Manipur. (2) The slug shape `<short>-<eci_code>` had to fall back to `dmk-dmk` for the ~12 top-20 parties whose `eci_codes` cell is blank in `parties.csv` (DMK, AAP, BSP, SP, JDU, JDS, TDP, YSRCP, SHS, NCP, BJD, LJP). The disambiguator did no work for the rows that needed it most. User direction (2026-06-12): follow the indiavotes model — top-level `/parties` index, per-party page at `/parties/<slug>` showing both national LS and state assembly performance — and no strangler-fig nonsense, rip-and-replace.

**Decision.** Five rules, each authored from one of the four 2026-06-12 persona verdicts (Hans / Fowler / Jony / Max).

(1) **Per-party page is party-scoped, not state-scoped.** Canonical URL = `/parties/<slug>`. Per-state breakdown is a SECTION inside the page (state-tile-cartogram + per-state seats-over-time chart per Hans Q1+Q2 verdict), never a path segment. The state-scoped `/<state>/party/<slug>` route is DELETED, no citizen-facing redirect (yen-gov has approximately zero external citations per the PR-P4 precedent). Per the user 2026-06-12 "no strangler-fig nonsense; rip-and-replace; temporarily breaking things is acceptable."

(2) **Slug shape is the lowercased `party_id` tail with `_` -> `-`.** Examples: `parties.IN.INC` -> `/parties/inc`; `parties.IN.AIADMK` -> `/parties/aiadmk`; `parties.IN.BSP_A` -> `/parties/bsp-a`; `parties.IN.CPI_ML_L` -> `/parties/cpi-ml-l`; `parties.IN.SHS_UBT` -> `/parties/shs-ubt`. Unique by construction (verified 2026-06-12: 2259/2259 unique tails across `datasets/data/entities/parties.csv`). Fowler verdict 2: pick the slug that's unique by construction over the one that's unique by convention; the cheapest collision test is the one that's a typing error in the data layer, not a runtime assertion. The rejected `<short>-<eci_code>` and `in-inc` shapes are recorded under ADR-0053 rejected alternatives below.

(3) **Sentinel slug overrides.** Three sentinel rows in `parties.csv` carry `is_sentinel = true`. Override map:
   - `parties.IN.IND` -> `/parties/independent` — Hans verdict 5: "IND" is publisher shorthand; "independent" is the noun the citizen reads when sharing the link.
   - `parties.IN.NOTA` -> `/parties/nota` — bare-tail default; citizen recognition is on the acronym; the page MUST surface the *PUCL v. Union of India 2013* legal-context caveat per Hans verdict 5.d (deferred to a follow-up PR per the plan-doc section 2; v1 page renders the same shape with honest framing). The page MUST also surface that NOTA is NOT a counted negative vote — even if NOTA leads, the leading candidate is still elected.
   - `parties.IN.UNK` -> NO PAGE (no citizen entity; resolver fallback per the no-silent-demotion rule, CLAUDE.md §10). `link.party("parties.IN.UNK")` returns `null`; callers render `party_short_raw` as plain text.

   Plus four non-sentinel disambiguators caught by the Tier-A 6-way disjointness contract:
   - `parties.IN.AC` (Arunachal Congress) -> `/parties/arunachal-congress` — bare tail `ac` collides with the RESERVED `ac` chrome token.
   - `parties.IN.GOA` (Goemcarancho Otrec Astro, Goa) -> `/parties/goemcarancho-otrec-astro` — bare tail `goa` collides with the state slug `goa`.
   - `parties.IN.MAHAD` (Mahakranti Dal, UP) -> `/parties/mahakranti-dal` — bare tail `mahad` collides with the AC slug `mahad` (Maharashtra constituency no. 194).

   The fourth disambiguator is `parties.IN.JIND` -> `/parties/jind-party`: bare tail `jind` collides with the current Haryana AC slug `jind`; parties.csv has no useful full-name expansion (`full` is `NA's`), so the override uses an explicit namespace suffix.

   Same citizen-framing doctrine in every case: when the bare tail collides with a reserved token / state slug / AC slug, spell out the full party name. The disjointness test pins this invariant so new collisions surface at PR-time, not citizen-time.

(4) **Flat namespace; no national/state path discrimination.** `/parties/<slug>` for every party regardless of `recognition_scope`. Putting recognition in the path freezes citizen bookmarks against ECI reclassifications (AAP went state -> state+Punjab -> national 2013->2017->2024; baking the classification into the URL re-violates the URL-stability contract ADR-0028 just locked in). Recognition badge lives in page chrome only. Hans verdict 4.

(5) **6-way disjointness contract.** Top-level `parties` (plural) is reserved in `RESERVED_PATH_TOKENS`; the legacy singular `party` (state-scoped sub-namespace marker) is dropped in the same atomic PR. `frontend/src/contracts/url-namespace-disjointness.test.ts` extends from 5-way to 6-way pairwise: party slugs are disjoint from `{stateSlugs, topicSlugs, acSlugsAcrossAllStates, urlIndicatorSlugs, RESERVED}` AND internally unique. STOP-AND-SURFACE rule: on any future collision the resolution is ALWAYS to fix the party slug (rename the party_id tail OR add a sentinel override in `slug.ts`) — NEVER add an exception to the test. Fowler verdict 5 + Hans verdict 6.

**Page surface contract** (Jony verdicts B1+B5+B7, executable in PR-4 of the plan-doc). Section order:
1. Header card: 80px coloured square (anchor=full-bleed, brand=ring, fallback=swatch, sentinel=grey-neutral) + party full name H1 + sub-line "<recognition> · peak <N> LS seats in <YYYY>".
2. Latest-of one-liner per body: "Lok Sabha (2024): **99 of 543 seats** · 21.2% vote share · ↓ from peak 415 in 1984."
3. KPI strip 2×2: LS seats, VS seats, elections contested, active range.
4. LS DualAxisBarLine chart (bars=seats, line=vote_share_pct).
5. VS DualAxisBarLine chart (parallel; only when body has data).
6. Top-10 strongholds per body (list + tiny W/L sparkline; constituency choropleth deferred per Jony B3).
7. Metadata footer with lucide glyphs: founded (calendar), dissolved (x-circle when set), recognition (landmark), home_state (map-pin), native_script (languages), wiki (external-link), predecessor/successor lineage chips.

The DualAxisBarLine renderer is a NEW closed-renderer entry (per [docs/concepts/schema-is-the-design-system.md](../../concepts/schema-is-the-design-system.md)); its own ADR ships with PR-4 of the party-rendering plan.

**PartyPill standardisation** (PR-1 + PR-2 of the plan-doc). The existing 4-tier `PartyPill` (anchor full-bleed / brand paper+ring / fallback paper+swatch / neutral grey) gains a hover/focus/click-pin tooltip popover. Tooltip content per Jony A2: symbol (when present; NO placeholder per the user-stated rule), short, full name, founded year, dissolved year (only if non-null), recognition badge, native script (italic), wiki external-link. The "Chief / President" line from indiavotes is NOT shipped (no `chief` column in parties.csv; Max section 3 ruled don't-fabricate). Every citizen-facing party reference (CompareElections winner table, IndiaPartyMap legend, NationalElection top-parties, PartyBar segments, WinnerBadge, StateOverview party-totals, Constituency candidate rows) renders via `<PartyPill>` and links to `/parties/<slug>` unless explicitly excluded (KPI numerators, sort column headers, breadcrumb labels — the four documented exceptions in [party-rendering.md](party-rendering.md)).

**Consequences.** URL is OWID-aligned (parties are an entity class peer to states; `/parties` is the alphabetical index per the OWID `/grapher/` precedent). Slug is unique by construction; the test-author never re-audits collisions on a new ingest. The state-scoped `/<state>/party/<slug>` URLs break for one release window between PR-0 and PR-2 of the plan (visible to citizens during that window as the per-party stub page); per the user 2026-06-12 acceptable. PartyPill becomes the SINGLE coloured party-rendering primitive across all citizen surfaces; the closed-renderer-doctrine bar for any future per-view bespoke chip is now formally raised. The 6-way disjointness contract grows by one TypeScript loader (`loadPartySlugs()`) + one describe block.

## Rejected alternatives

This section preserves the rejected-alternatives receipts for the ADRs whose rationale is folded above, verbatim and append-only per the ADR retirement contract ([decision-index.md](../../reference/decision-index.md)). Each subsection is anchored as `#adr-NNNN-rejected-alternatives` (or `#adr-NNNN-<disambiguator>-rejected-alternatives` for the disambiguated 0016) for the redirect index. The archived [ADR-0016 frontend-hash-routing](../../archive/decisions/0016-frontend-hash-routing.md) trace lives here per [decision-index.md](../../reference/decision-index.md) (the archived body is preserved verbatim under `docs/archive/decisions/`).

### ADR-0028 rejected alternatives

Verbatim from the originating ADR. Append-only per ADR retirement contract.

1. **Original `/c/<country>/s/<state>/[d|ac]/<seat>/i/<id>` cascade.** Rejected by user as "over complicating"; markers don't earn their place when slug shapes already disambiguate.
2. **`?i=<indicator>` query-string projection.** Rejected by user explicitly - indicator must live in the path.
3. **`/i/<indicator-id>` reserved-marker scheme (Gregor + Fowler round 2).** Dissolved by flat-slug move; also not OWID-aligned (OWID never uses a positional mid-cascade marker).
4. **Hash routing per ADR-0016.** Rejected - OWID-divergence on the most-visible surface; Jony's read-aloud test fails ("hash slash India"); link unfurl broken. See also [ADR-0016 frontend rejected alternatives below](#adr-0016-frontend-rejected-alternatives) for the archived hash-routing trace; path routing on Pages adopted per ADR-0028.
5. **AC number prefix `167-mylapore`.** Rejected by user - citizen does not navigate by ECI number.
6. **Preserve indicator slash hierarchy in path (`/india/tamil-nadu/power/installed-capacity`).** Rejected - Max's OWID precedent: topic re-homing breaks URL stability; flat slug is the durability bet.

### ADR-0037 rejected alternatives

Verbatim from the originating ADR. Append-only per ADR retirement contract.

1. **Keep ADR-0028 verbatim (`/india/<state>/...`).** Rejected - on a `.in` domain `/india/` reads as a stutter; yen-gov is India-only by [CLAUDE.md section 0 non-goals](../../../CLAUDE.md); paying one segment of URL tax on every page for an optionality we don't have is what gets deleted.
2. **Keep the shipped `/s/<state>/...` grammar (Grammar B).** Rejected - `/s/` and `/ac/` are positional markers that don't disambiguate (state slugs are disjoint from AC slugs by construction); markers that don't disambiguate read as scaffolding.
3. **Hive partition form `/s/in_s33/167/...`.** Rejected - Hive partition keys are a filesystem dialect, not a citizen sentence; already rejected by `frontend/src/lib/slug.ts` and not re-litigated.
4. **Topic landing at root (`/energy` not `/t/energy`).** Rejected - even when topic slugs don't collide with state slugs today (they don't: `energy`, `fiscal`, `health` vs `tamil-nadu`, `gujarat`), dropping `/t/` forces the root resolver to consult three registries per navigation AND makes every future topic-name addition a state-collision audit. The 2 characters of `/t/` buy permanent topic-namespace freedom.
5. **Per-state topic at `/<state>/<topic>` (flattening the per-state `/t/`).** Deferred - Phase 1 `links.ts` ships `/<state>/t/<topic>`. Decision needed before Phase 2 route-table change.

### ADR-0052 rejected alternatives

ADR-0052's body is structured around POSITIVE decisions (path-encodes-identity rule + four numbered sub-decisions) rather than a separate `## Alternatives considered` section. The receipts that survive as rejected approaches are the two-grammar status quo + the one-release legacy-honour shape, preserved verbatim from the originating ADR context. Append-only per ADR retirement contract.

- **Keep two URL grammars for one election resource** (`/s/<state>/ac/<n-slug>?event=<event>` for the constituency drill-down AND `/s/<state>/elections/<event>` for the state overview, with event in the query string on one and the path on the other). Rejected by user: "I don't see a reason for having two url patterns for the same data, it makes it harder to maintain two surfaces." Two URL grammars for one logical thing is more to maintain and reason about, and blurs the line between "which resource am I looking at" (identity) and "how am I looking at it" (view-state).
- **Treat the bare `/s/<state>/ac/<n-slug>` as a canonical resource (no redirect).** Rejected: it carries no election in its path, so it is not identity-complete. Allowing it as canonical would mean every constituency page implicitly answers for whatever the state's current default event is, with no shared-URL stability across cohort transitions. Keeping it as a convenience entry that `replaceState`-redirects to the nested canonical form preserves the path-encodes-identity invariant while giving citizens a short-URL on-ramp.
- **Hard-fail or delete legacy `?event=` bookmarks immediately.** Rejected: pre-ADR-0052 shared links exist; one-release strangler-fig honouring (read the query event, resolve, `replaceState` to the path form) covers the migration without breaking external citations. The query form is not emitted by any builder; the reader merely accepts it for one release.

### ADR-0053 rejected alternatives

Verbatim from the originating ADR (the 2026-06-12 persona verdicts that authored ADR-0053 above). Append-only per ADR retirement contract.

- **State-scoped per-party URL `/<state>/party/<slug>` (the legacy grammar).** Rejected by Hans verdict 1: a citizen searches for a party as a noun (an actor in democracy), not as a per-state per-year measurement; the URL must name the actor and let the page enumerate the per-state per-year facts. Also rejected on shared-link grounds: a DMK link shared on WhatsApp should mean DMK, not DMK-in-some-state. Note from Fowler verdict 6: this is exactly the failure mode the rip-and-replace topology is most at risk of half-implementing — keeping the state-scoped resolver alongside the new party-scoped page would produce a single Svelte component that half-renders both surfaces depending on which route mounted it. PR-0 deletes the state-scoped grammar atomically.
- **One-release client-side redirect from `/<state>/party/<slug>` -> `/parties/<slug>`.** Rejected per user 2026-06-12 ("no strangler-fig nonsense; rip-and-replace; temporarily breaking things is acceptable") and per the PR-P4 precedent (the equivalent `/s/*` Grammar-B redirect tombstone was deleted on 2026-06-10 with the explicit policy "Legacy bookmarks fall through to NotFound"). yen-gov has approximately zero external citations today; the redirect would be rent paid for nobody.
- **Slug shape `<short>-<eci_code_lower>` (today's `/<state>/party/dmk-5` form).** Rejected by Hans verdict 3 + Fowler verdict 2: ADR-0028's AC-slug rejection of `167-mylapore` ("citizen does not navigate by ECI number") applies verbatim and arguably more strongly to parties (nobody knows "BJP is ECI registration 369"). Worse: many top-20 parties (DMK, AAP, BSP, SP, JDU, JDS, TDP, YSRCP, SHS, NCP, BJD, LJP) have an EMPTY `eci_codes` cell in parties.csv, so today's slug had to fall back to `dmk-dmk` — the disambiguator did no work for the rows that needed it most.
- **Bare-short slug (`/parties/inc`, `/parties/dmk`).** Rejected by Fowler verdict 2: parties.csv has collision-prone `short` fields (e.g. `CPI(ML)L` and `CPI(ML)( L)` both slugify to `cpi-ml-l`); empty-short rows exist for sentinels. Bare-short would require either an emit-time slug-uniqueness check OR a `<short>-2` collision fallback (same anti-pattern as AC slugs, which the canonical-store has since proven to be a recurring data-drift hazard — every new ingest can re-shuffle which party is "first"). The party_id-tail shape is unique by construction.
- **`/parties/in-inc` (canonical party_id transliterated).** Rejected on the same stutter-scaffolding grounds that killed `/india/` from indicator URLs in ADR-0037: the `in-` prefix reads as a country marker on a `.in` domain. Lowercased tail is the citizen-readable shape.
- **Scope-discriminating URL (`/parties/national/inc` vs `/parties/state/dmk`).** Rejected by Hans verdict 4 on three grounds: (i) `recognition_scope` is FLUID — AAP went state -> state+Punjab -> national-recognised (2013 -> 2017 -> 2024); baking it into the URL means a citizen bookmark to last year's classification breaks. (ii) JD(U)'s `home_state_codes = IN-AR|IN-BR|IN-MN`; which state goes in the URL? Putting JD(U) at `/parties/bihar/jdu` misleads; putting it at `/parties/national/jdu` is just false. The discrimination is not a clean partition for ~30 of the parties citizens actually search for. (iii) Per ADR-0037 doctrine, "markers that don't disambiguate read as scaffolding"; the same logic that deleted `/s/` and `/ac/` applies.
- **Nest under `/t/parties` (topic-shaped).** Rejected by Hans verdict 6: parties are an ENTITY CLASS (peer to states and indicators), not an indicator family. Topics in the topic catalogue are indicator families (energy, fiscal, health, demography); parties are political actors that appear AS DIMENSIONS on election indicators. Shipping `/t/parties` would dilute the topic catalogue's meaning and create a one-entry, no-siblings category.
- **`/parties/unknown` page for the UNK resolver-fallback.** Rejected per Hans verdict 5: UNK is operator telemetry ("yen-gov could not resolve this party's identity"), NOT a citizen entity. The PartyPill for a row resolved to UNK renders `party_short_raw` as plain text (publisher's verbatim label) with no link.
- **Add a `chief` / `president` / `leader` column to parties.csv to ship the indiavotes-style "Chief: <name>" tooltip line.** Rejected (deferred to a separate Wikidata P488 ingest PR) per Max section 3: parties.csv has no `chief` column today; modelling party officers needs a `office_holdings.csv` extension with term-shape (party presidents come and go), not a single-string column on parties.csv. The tooltip drops the line rather than fabricate it.
- **Backend-precomputed `parties-index.csv` with `seats_won_total` / `last_active_year` columns for sort.** Rejected per Fowler verdict 4: `seats_won_total` is DERIVED data not reference data; baking it into a CSV at backend time creates a hand-authored value that contradicts the canonical answer DuckDB would compute over `election_results.csv`. At 2259 parties × ~18 columns the CSV is <200KB and DuckDB-WASM handles direct queries in single-digit ms; precompute is the "build the perf optimisation before measuring the problem" trap.

### ADR-0016 frontend rejected alternatives

Verbatim from the archived [ADR-0016 frontend-hash-routing](../../archive/decisions/0016-frontend-hash-routing.md) (body preserved verbatim under `docs/archive/decisions/`). Append-only per ADR retirement contract.

- **svelte-routing / svelte-spa-router (rejected at ADR-0016 time as router-lib choice).** Viable, but adds a dependency and an opinion (slot-based routing, named params with `:slug` syntax, etc.) for a 4-route app. Rejected on YAGNI. (Context-of-rejection note: when ADR-0028 superseded the routing-mode decision, the project DID adopt `svelte-spa-router` for its pattern-based dispatch - the YAGNI rejection at the 4-route scale flipped at the 50-route scale, which is the same logic that flipped the 404.html shim.)
- **SvelteKit with adapter-static (rejected at ADR-0016 time).** Gives us file-system routing and SSG. Rejected because (a) Holy Law #1 forbids assuming any backend, and adapter-static is a heavy migration path; (b) we already have a working Vite + plain-Svelte setup; (c) routing is the only thing SvelteKit would buy us right now. This rejection still stands at ADR-0028 time and beyond - the project remains Vite + plain-Svelte for the canonical SPA setup.
- **History-mode custom router + 404.html shim (rejected at ADR-0016 time; ADOPTED by ADR-0028).** Pretty URLs, but every deep-link load goes through a redirect. Rejected on the brittleness called out in Context. (Context-of-rejection note: ADR-0028 explicitly reverses this rejection - the shim's "perpetual footgun" framing was wrong at present scale, and the OWID precedent + the shareability contract make path routing the load-bearing choice. The 5-line shim cost is less than the link-unfurl cost of hash routing. This bullet remains as the original rejected alternative for trace integrity.)
- **Hash routing itself (the ADR-0016 decision, now superseded).** Rejected by ADR-0028 on three grounds preserved here for the trace: (i) breaks link unfurls (Telegram/WhatsApp/Slack OG scrapers see only `/`); (ii) inconsistently indexed by search engines; (iii) reads as "broken" to citizens copying URLs. Jony's read-aloud test fails for hash routing ("hash slash India"). One-release-cycle strangler-fig redirect (`#/...` -> path form) covers the migration; deleted after.

## Named divergences from canonical URL grammar

Two narrow elections-only divergences from ADR-0028 / ADR-0037 are locked here. Both are scoped to the elections surface and do not relax any invariant the canonical grammar holds for socio-econ indicators.

### Event-grain URLs (elections-only exception, PR-0 2026-06-09)

**Context.** ADR-0028 rejected vintage-in-URL ("no vintage in path; `?as_of=` for citation only"). The election-cohort identifier (`general-2024`, `assembly-2023`) reads superficially like vintage but is not. Vintage is "which snapshot of the same fact" - re-publishing the 2011 Census tomorrow at a new vintage MUST not produce a new URL because it is the same fact. Election cohort is "which dated act of voting produced this result" - the May 2026 Tamil Nadu Assembly contest is a different event from the May 2021 contest; one URL describing both is the federal falsehood ADR-0023 already rejected. Event is identity, not vintage.

**Decision.** Event-cohort identifier is a permitted path segment on the elections surface only. The full cascades, the citizen contract:

```
/t/elections                                                  -> firehose (all events ever, sortable)
/t/elections/<event-slug>                                     -> national event view
/<state>/elections/<event-slug>                               -> state slice of one event
/<state>/elections/<event-slug>/<constituency-slug>           -> constituency drill (no /pc/, no /ac/)
/compare/elections/<state>/<from-event-slug>/<to-event-slug>  -> body-tagged event-vs-event compare
/lab/<state>/<event-slug>                                     -> analyst surface (scenarios ephemeral; no ?s=<b64>)
```

Event-slug grammar (locked):

```
general-<YYYY>                                  e.g. general-2024
assembly-<YYYY>                                 e.g. assembly-2023
general-bye-<YYYY>-<state-slug>-<seat-slug>     e.g. general-bye-2024-bihar-bastar
assembly-bye-<YYYY>-<seat-slug>                 e.g. assembly-bye-2024-tarikere  (state in path)
```

Regex pin (enforced by [url-namespace-disjointness.test.ts](../../../frontend/src/contracts/url-namespace-disjointness.test.ts) since PR-0): `^(general|assembly)(-bye-[a-z0-9-]+|-\d{4})$`. Body prefix (`general-` / `assembly-`) carries the constituency type at the leaf - the legacy `/pc/` and `/ac/` literals are dropped. Body roots `/parliament/` and `/assembly/` are NOT minted; body distinction lives only in the slug prefix.

**Disjointness against the event-context literals.** The set `{"general", "assembly", "elections"}` appears as path segments in the elections cascade (literal `/elections/` middle segment and event-slug body prefixes). State slugs and AC slugs MUST be pairwise disjoint from the full set so a 1-segment URL like `/general` cannot be misread as a state hub. Topic slugs are disjoint from the narrower `{"general", "assembly"}` set only - the topic id `elections` IS valid today (the elections topic family is a real topic) and its `/t/elections` URL is superseded by the firehose via route-table order (PR-W3d registers `/t/elections` ahead of `/t/:topic`); only `general` and `assembly` have no legitimate topic identity. The disjointness contract test extends to assert this since PR-0; `elections` is NOT added to `RESERVED_PATH_TOKENS` because the firehose stays at the existing `/t/elections` (top-level reservation `t` covers it).

**No legacy-URL absorber.** Old `?s=<b64>` and `LsGenJun2024`-style URLs are not redirected; bookmarks lose work. Acceptable today; revisit when a real citizen complaint surfaces.

### English-only citizen-chrome policy (PR-0 2026-06-09)

**Context.** Pre-2026-06 the elections surface mixed English with transliterated tokens from one local language: `kind: "lok_sabha"` / `"vidhan_sabha"` in TypeScript enums + JSON schema + Python labels; "Lok Sabha" / "Vidhan Sabha" in citizen-facing chrome strings. Transliterated tokens in URLs / chrome / code break the read-aloud test for the median Indian citizen (who reads English on the web but speaks one of 22 scheduled languages at home), break URL-slug derivation (`lok_sabha` is not a stable slug; ECI publishes editions in multiple scripts), and bake one language's vocabulary into the spine of an India-wide federal site. Hans-led debate converged: English nouns for code + URL; transliterated tokens allowed only as one Glossary line in page body (never slug / heading / code).

**Decision.** English-only across:

- **URLs** - event-slug body uses `general` (Parliament cohort) / `assembly` (state Assembly cohort); never `lok-sabha` / `vidhan-sabha`. Slug grammar locked above.
- **Chrome strings** - page titles, KPI labels, chart axes, button captions use "Parliament", "Assembly", "General Election YYYY", "<State> Assembly Election YYYY". Never "Lok Sabha" / "Vidhan Sabha" / "Vidhan Parishad".
- **Code identifiers** - `kind` enum on `election-events.schema.json` is `"parliament" | "assembly" | "general_bye" | "assembly_bye"`. TypeScript `EventKind` union, Python adapter labels, test fixtures, comment prose all match.
- **Event-id literals** - `general-2024` / `assembly-2023` per slug grammar above.

**Carve-outs.** Constituency-unit nouns "Parliament constituency" / "Assembly constituency" appear in chrome where the per-seat context is needed; the short forms "PC" / "AC" survive in URL slugs (the `<constituency-slug>` leaf), CSV column names (`entity_kind: "ac" | "pc"`), and chart axes. One Glossary line in page body MAY name the local-language synonym ("Parliament constituency (Lok Sabha)", "Assembly constituency (Vidhan Sabha)") for citizens who learned the local-language term first; never in slug, heading, or code.

**Mechanical scrub gate.** PR-W1a executes the repo-wide rename + ships a grep gate: `git grep -iE "lok.sabha|vidhan.sabha"` MUST return zero matches across `frontend/src/`, `backend/yen_gov/`, `datasets/schemas/`, `datasets/taxonomy/`, and `docs/`. After PR-W1a the gate is the doctrine; doctrinal rejection of any PR that reintroduces a transliterated token from a local language in slug / chrome / code (one-line Glossary body carve-out aside).

## See also

- [docs/architecture/frontend/routing.md](routing.md) - the operational route resolver (router patterns, registry lookups, RESERVED_PATH_TOKENS, missing-scope stub behaviour).
- [docs/concepts/place-first-ia.md](../../concepts/place-first-ia.md) - the IA spine (ADR-0022) that this URL grammar implements at the route layer.
- [docs/concepts/owid-alignment.md](../../concepts/owid-alignment.md) - the fallback doctrine that this URL grammar exemplifies (and re-applies at ADR-0037).
- [archived ADR-0016 - frontend-hash-routing](../../archive/decisions/0016-frontend-hash-routing.md) - body preserved verbatim; rejected-alternatives trace folded above.
- [decision-index.md](../../reference/decision-index.md) - the redirect index pinning every ADR to its new doc anchor.
- [frontend/src/lib/links.ts](../../../frontend/src/lib/links.ts) - Grammar A builders (Phase 1 of ADR-0037).
- [frontend/src/contracts/url-namespace-disjointness.test.ts](../../../frontend/src/contracts/url-namespace-disjointness.test.ts) - the namespace disjointness Tier-A contract test.
- [frontend/src/contracts/state-slugs-full-name.test.ts](../../../frontend/src/contracts/state-slugs-full-name.test.ts) - the full-name state-slug invariant Tier-A contract test.

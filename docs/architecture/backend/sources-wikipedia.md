# Backend `sources/wikipedia/` — Wikipedia Source Adapter

**Last Updated**: 2026-05-22

> **District adapter retired in T.0c-iii Phase D.1** (2026-05-22; see [ADR-0033](../decisions/0033-retire-wikipedia-districts-adapter.md)). The `districts.py` parser, `districts_url()` builder, and `DistrictsCollection` / `DistrictEntry` models are gone. District identity now lives as `entity_type='district'` rows on `datasets/taxonomy/entities.json`, sourced from the LGD (Local Government Directory, MoPR) per CLAUDE.md §3. The constituencies parser keeps its two-pass district-name resolver; the only change is that the input lookup dict is now built from entities.json (see [District-name resolution for AC tables](#district-name-resolution-for-ac-tables)).

`backend/yen_gov/sources/wikipedia/` is the adapter for the English Wikipedia. It supplies *reference* data ECI does not publish in machine-readable form: per-state assembly constituencies with reservation status. It also implements a heuristic district-name resolver to bridge spelling drift between Wikipedia's AC table and the entities.json display names.

Wikipedia is a **bootstrap source**, never the only source for a `status: complete` reference file (see also: [authority hierarchy](sources-eci.md#authority-hierarchy-for-past-elections)).

## Modules

| File | Responsibility |
| ---- | -------------- |
| [`urls.py`](../../../backend/yen_gov/sources/wikipedia/urls.py) | URL builders + ECI-state-code → Wikipedia-article-name map. |
| [`constituencies.py`](../../../backend/yen_gov/sources/wikipedia/constituencies.py) | Parses `List of constituencies of the <State> Legislative Assembly` → `ConstituenciesCollection`. Includes `build_district_lookup()` two-pass resolver. |

## URL building

State-name routing is an explicit dict in `urls.py`:

```python
_ECI_TO_WIKI_STATE = {"S22": "Tamil Nadu", ...}
```

Adding state support means adding the entry. We chose explicit lookup over generic name normalisation because (a) the set is finite (36 states/UTs), (b) Wikipedia article names occasionally differ from official English names ("Odisha" vs older "Orissa" redirects), and (c) a missing entry must fail loudly with a `ValueError`, not silently 404.

This dict is *adapter-local routing data*, not user-facing taxonomy (CLAUDE.md §6). The user-facing names live in `entity.schema.json`-validated content (`datasets/taxonomy/entities.json`; pre-Phase-C the comparable file was the retired `state.schema.json`-validated `reference/in/states.json`).

## User-Agent

`en.wikipedia.org` returns 403 to default httpx User-Agents. The Wikipedia API etiquette page asks for a descriptive UA identifying the project and a contact URL. Tests and the pipeline both send:

```
yen-gov/<version> (https://github.com/miztiik/yen-gov; election data pipeline) httpx
```

Test code carries the same string; bot-mitigation is per-UA, not per-IP.

## District parser — retired

The two-pass `parse_districts()` with predecessor resolution was deleted in T.0c-iii Phase D.1 (ADR-0033). District identity is now hand-curated on `datasets/taxonomy/entities.json` with `entity_type='district'` rows carrying `legacy_id` (the 3-letter wikipedia-derived code preserved for constituencies.json cross-references) and `lgd_code` (the LGD source of truth per CLAUDE.md §3). New district inserts / splits are pull requests against entities.json, not re-scrapes.

## Constituency parser — minimal per-row data

The page's first wikitable carries `# | Constituency | Reserved | Electors | Change | District | …`. We extract only the first three columns and emit `ConstituencyEntry(eci_no, name, reservation, district_id=None)`:

- Wikipedia uses rowspans for repeated district names, which lxml's `text_content()` does not unfold.
- ECI's spelling for districts varies ("Tirunelveli" vs "Thirunelveli"), so a string match against `district.json` ids would be brittle.
- `constituency.district_id` is *optional* in the schema. Filling it is a downstream concern (see [district-name resolution](#district-name-resolution-for-ac-tables) below).

Reservation tokens are normalised explicitly:

| Wikipedia cell | Normalised |
| -------------- | ---------- |
| `-`, `—`, `–`, blank, `GEN`, `General`, `None` | `GEN` |
| `SC`           | `SC`       |
| `ST`           | `ST`       |
| anything else  | **raises** `ValueError` |

A new reservation code (e.g. a Wikipedia editor invents `Backward`) must surface as a parser failure rather than be silently coerced.

The constituency parser asserts that the parsed AC numbers form a contiguous `1..N` sequence. A missed row or duplicate would otherwise quietly land in the artifact.

All Wikipedia-bootstrapped constituency files are emitted with `status: "provisional"` per [constituency hierarchy & status lifecycle](../data-model.md#constituency-hierarchy-and-status-lifecycle). Wikipedia alone cannot promote a file to `complete`.

## District-name resolution for AC tables

Wikipedia's "List of constituencies of the X Legislative Assembly" tables carry a District column whose strings do not match the canonical district display names 1:1. Real cases observed in TN + KL:

| AC table writes  | entities.json `display_name`|
| ---------------- | --------------------------- |
| `Thiruvallur`    | `Tiruvallur`                |
| `Tirupattur`     | `Tirupathur`                |
| `Kanniyakumari`  | `Kanyakumari`               |
| `Chennai`        | `Chennai (formerly Madras)` |
| `Kasargod`       | `Kasaragod`                 |

These are not data errors — Indian district names have multiple defensible romanisations; different Wikipedia editors picked different ones. A naive casefolded equality check resolved 192 of 234 TN ACs and 135 of 140 KL ACs, leaving 47 unresolved across two states.

A two-pass resolver in `sources.wikipedia.constituencies`:

1. **Exact key**: `_strip_parens(name).casefold().strip()` — handles the parenthesised-suffix case (`Chennai (formerly Madras)` → `chennai`).
2. **Skeleton key**: a deterministic `_norm()` that lowercases, drops non-alpha, removes every `h`, removes vowels after the first character, and collapses repeated letters. Designed to make `Thiruvallur` / `Tiruvallur` / `Tirupathur` / `Tirupattur` / `Kanniyakumari` / `Kanyakumari` / `Kasargod` / `Kasaragod` all collide with their counterpart on the entities-side display name.

`build_district_lookup()` indexes each district under **both** keys so callers see a single dict-of-strings interface.

The input pair-list `[(display_name, legacy_id), ...]` is built by `pipeline/reference.py:_district_lookup_from_entities()` from `datasets/taxonomy/entities.json`, filtering to `entity_type='district' AND parent_entity_id=f'IN-{state}' AND legacy_id IS NOT NULL AND entity_valid_to IS NULL`. Pre-Phase-D.1 the same lookup was built from a freshly-scraped districts.json (`build_district_lookup([(d.name, d.id) for d in districts.districts])`); the resolver itself is unchanged.

If both passes miss, `district_id` is left absent — the entry stays valid under the provisional schema, and the unresolved cell is silently tolerated. We do not promote `status` to `complete` on Wikipedia data alone (that requires `pc_id` too, which Wikipedia AC tables don't carry). Known structural gaps: Puducherry (U07) Mahe and Yanam districts are not enumerated by LGD as standalone districts, so they are absent from entities.json and ACs in those regions land with `district_id=null` until a manual override or a non-LGD source fills the gap. Acknowledged in CLAUDE.md §3's never-invent-ids rule.

### Resolver rationale

The rules give 100% resolution on TN (234/234) and KL (140/140) without per-state alias tables, and they're general (not state-specific) so new states should mostly work without adjustment. Status stays `provisional` until an authoritative ECI cross-check fills `pc_id`.

Acknowledged costs:

- The skeleton can in principle collide between two genuinely different districts that share a consonant skeleton. Mitigation: `build_district_lookup()` uses `setdefault`, so the first-registered district wins, and the lookup is built per-state (collision risk is bounded by the ~38 districts in the largest state we'll see).
- Heuristic rules will need tuning for north-eastern states (Khasi/Garo/Mizo names) where vowel-collapse may collide. We accept that and will revisit when those states are onboarded.

## Design rationale

- TN-only first slice can ship: districts.json + constituencies.json + everything ECI-derived. Other states unblocked by adding one URL-map entry.
- Parser failures are loud — tests catch reservation-token surprises and missing rows in CI's live tests.
- Zero coupling to `core.http.Fetcher`. The parser takes bytes; the orchestrator decides where they came from.

Acknowledged costs:

- Wikipedia drift (table reorganisations, header renames) breaks our parsers. Mitigated by header-text matching being lenient ("estd" or "established", any "reserv*" header) and live tests catching the change before code that consumes the artifact runs.
- District resolution for constituencies is heuristic until LGD codes land. `district_id` will stay `None` for any AC the resolver can't match.

The following two subsections consolidate the Context + Decision + Consequences of the originating ADRs that pinned cross-cutting choices for this adapter (district-name resolution; retiring the districts sub-adapter); the originating ADR files under `docs/architecture/decisions/` were deleted in [docs/archive/plans/20260604-d-doc3-adr-retire-subplan.md](../../archive/plans/20260604-d-doc3-adr-retire-subplan.md) D-DOC3.10 closure. The redirect map lives at [decision-index.md](../../reference/decision-index.md). Folded into this doc per D-DOC3.8 (2026-06-04).

### ADR-0018: wikipedia-district-name-resolution

Status: accepted 2026-05-09.

**Context.** [ADR-0015](../../concepts/electoral-hierarchy.md#adr-0015-constituency-hierarchy-fields) added `district_id` as an optional field on `ConstituencyEntry`, populated when an authoritative source maps an AC to its parent district. The Wikipedia "List of constituencies of the X Legislative Assembly" tables already carry a District column, but the strings in that column do not match the names emitted by `parse_districts` 1:1. Real cases observed in TN + KL pages: `Thiruvallur` vs `Tiruvallur`, `Tirupattur` vs `Tirupathur`, `Kanniyakumari` vs `Kanyakumari`, `Chennai` vs `Chennai (formerly Madras)`, `Kasargod` vs `Kasaragod`. These are not data errors - Indian district names have multiple defensible romanisations; different Wikipedia editors picked different ones. A naive casefolded equality check resolved 192 of 234 TN ACs and 135 of 140 KL ACs, leaving 47 unresolved across two states.

**Decision.** A two-pass resolver in `sources.wikipedia.constituencies`: (1) exact key `_strip_parens(name).casefold().strip()` handles the parenthesised-suffix case; (2) skeleton key `_norm()` lowercases, drops non-alpha, removes every `h`, removes vowels after the first character, and collapses repeated letters, designed to make the romanisation pairs above all collide with their counterpart on the canonical side. `build_district_lookup()` indexes each district under BOTH keys so callers see a single dict-of-strings interface. If both passes miss, `district_id` is left absent - the entry stays valid under the provisional schema, and the unresolved cell is silently tolerated. We do not promote `status` to `complete` on Wikipedia data alone (that requires `pc_id` too, which Wikipedia AC tables don't carry). Full operational mechanics live in [District-name resolution for AC tables](#district-name-resolution-for-ac-tables) above.

**Consequences.** 100% resolution on TN (234/234) and KL (140/140) without per-state alias tables; the rules are general (not state-specific) so new states should mostly work without adjustment; status stays `provisional` until an authoritative ECI cross-check fills `pc_id` (keeps the lifecycle honest). Costs: the skeleton can in principle collide between two genuinely different districts that share a consonant skeleton (mitigation: `build_district_lookup()` uses `setdefault`, first-registered district wins, lookup is built per-state); rules are heuristic and will need tuning for north-eastern states (Khasi / Garo / Mizo names) where vowel-collapse may collide - revisit when those states are onboarded.

### ADR-0033: retire-wikipedia-districts-adapter

Status: accepted 2026-05-22. Deciders: User (autonomous per the explicit "make good decisions" + "take help of the custom agents" delegation in this session) + Hans (Governance) + Max (Indicator Scout) + Gregor (Architect) - three custom agents consulted in parallel; unanimous recommendation D.1.c.

**Context.** T.0c-iii Phase A (PR #81, commit `a3d45611`) folded the 145 current districts from the 6 per-state `datasets/reference/in/states/<S>/districts.json` files INTO `datasets/taxonomy/entities.json` as `entity_type='district'` rows, each carrying `legacy_id` (the 3-letter wikipedia-derived code) and `lgd_code` (the LGD source-of-truth identifier per [CLAUDE.md section 3](../../../CLAUDE.md) "never invent IDs when an issuing authority publishes one"). Phase B (PR #82, commit `2c9d9712`) stripped the `districts.json` loader from `backend/yen_gov/taxonomy/entities_seed.py`; the `entities.parquet` SHA-256 stayed `771ECEC3...62243ED` byte-stable across both phases, proving zero data effect. Phase C audit (per the 2026-05-21 lesson "audit ALL of backend/, tools/, docs/, admin/ before `git rm` of any file under `datasets/`") surfaced 9 live consumers - most importantly an import-time crash risk: `backend/yen_gov/core/models.py:152` had `class DistrictsCollection(_Artifact): _schema_id = schema_id("district.schema.json")` at module scope, so deleting the schema file would have crashed every pytest collection across the entire backend. The remaining wikipedia districts subsystem after Phase B was a Bootstrap Filter (Hohpe, *Enterprise Integration Patterns*) that served exactly one purpose - bootstrap the districts.json files that seeded the canonical taxonomy - with seeding complete and entities.json now the source of truth, the adapter had ZERO downstream consumers.

**Decision.** Retire the wikipedia districts adapter entirely (D.1.c): delete `backend/yen_gov/sources/wikipedia/districts.py`, the `districts_url()` builder, the `DistrictEntry` + `DistrictsCollection` Pydantic models, the districts fetch+parse+write block from `pipeline/reference.py`, the "reference" CLI's districts echo, and the two associated tests. Rewrite the constituencies parser's district-name lookup to source `[(display_name, legacy_id), ...]` pairs from `datasets/taxonomy/entities.json` instead of from a freshly-scraped districts.json. The constituencies parser's two-pass `_strip_parens` + `_norm` heuristic district-name resolver itself is unchanged - only the input lookup dict's source changes (from a parsed `DistrictsCollection` to a filtered `entities.json` projection). The `build_district_lookup()` helper signature stays identical. Phase D.2 (PR #85, `95ba5d13`) then deleted `tools/lgd/backfill_lgd_codes.py`; Phase D.3 `git rm`-ed the 6 districts.json + `district.schema.json` + scrubbed live doc/plan references + amended `datasets/migration-ledger.csv` + recorded the Mahe / Yanam structural-gap acknowledgement in the commit body. Closes the T.0c-iii strangler-fig arc.

**Consequences.** Adapter surface area shrinks by ~250 LoC (parser + URL builder + model + fetch block + tests) with zero behavioural regression; one fewer outbound HTTP dependency on a per-state reference run; entities.json becomes the unambiguous source of truth for district identity; unblocks D.2 + D.3. Acknowledged loss: the Mahe and Yanam UT-sub regions of Puducherry (U07) are not enumerated by LGD as standalone districts, so they are absent from entities.json and ACs in those regions land with `district_id=null` on a fresh `yen-gov reference U07` run - the eventual fix is either an LGD revision that enumerates UT-sub regions or a manual override row in entities.json with an issuing-authority-defined identifier (acknowledged structural gap; documented in `_district_lookup_from_entities()` docstring and in [District-name resolution for AC tables](#district-name-resolution-for-ac-tables) above).

> **DOCTRINE NOTE (2026-06-04, plan section 22.7).** ADR-0033's retirement decision survives the broader data-platform reset verbatim - the wikipedia districts adapter is gone and stays gone. The constituencies adapter's local-CSV reingest pathway (plan chunk B4) does NOT re-introduce the deleted districts code; entities.json (or its long-format-CSV successor under `datasets/data/entities/`) remains the FK target for `district_id` resolution. The Mahe / Yanam structural gap is unchanged by the rip.

## Alternatives considered

### Adapter scope

- **Wikipedia REST/Action API instead of HTML scraping**. Rejected: the data we need lives in human-edited wikitables, not in structured infoboxes or Wikidata claims for these specific articles. Wikidata occasionally lacks reservation status entirely.
- **Wikidata SPARQL for ACs**. Rejected for now: Wikidata coverage of Indian electoral geography is uneven (some districts have items, some don't; reservation status is rarely modelled). Worth revisiting if/when coverage improves.
- **Generic `parse_wikitable(headers, content)` reused across pages**. Rejected: each page has page-specific concerns. A shared helper would be a thin wrapper over lxml that hides nothing.
- **Keep the wikipedia districts adapter as a fallback for states LGD hasn't seeded yet**. Rejected in T.0c-iii Phase D.1 ([ADR-0033](../decisions/0033-retire-wikipedia-districts-adapter.md)): districts.json is no longer a contract surface (it has zero readers post-fold-in to entities.json), so the adapter has no consumer. New districts land via a PR against entities.json with an LGD-issued `lgd_code` or, where LGD has a structural gap (Mahe / Yanam in U07), an explicit operator-curated entry.

### District-name resolver

- **Hand-rolled per-state alias tables** (`{"Thiruvallur": "TAL", ...}`). Rejected: hardcoding (CLAUDE.md Holy Law #6) and unbounded maintenance — every new state needs a fresh alias table built by hand.
- **Levenshtein/Damerau-Levenshtein fuzzy match with a distance threshold**. Rejected: introduces a dependency for a problem that's already solvable with deterministic string ops; thresholds are inherently fiddly.
- **Extract LGD codes from gov.in Local Government Directory and match those instead**. The right long-term answer (CLAUDE.md §13) — when LGD codes land we'll use those for both districts.json and the AC↔district join, and this resolver becomes the fallback for states the LGD scrape doesn't cover.

### ADR-0018 rejected alternatives

Verbatim from the originating ADR. Append-only per parent plan section 9 (keep-receipts).

- **Hand-rolled per-state alias tables** (`{"Thiruvallur": "TAL", ...}`). Rejected: hardcoding ([CLAUDE.md Holy Law #6](../../../CLAUDE.md)) and unbounded maintenance - every new state needs a fresh alias table built by hand.
- **Levenshtein / Damerau-Levenshtein fuzzy match with a distance threshold.** Rejected: introduces a dependency for a problem that's already solvable with deterministic string ops; thresholds are inherently fiddly and would need a bypass when a real district name is one edit away from another in the same state.
- **Extract LGD codes from gov.in Local Government Directory and match those instead.** The right long-term answer (CLAUDE.md section 13) - when LGD codes land we'll use those for both districts.json and the AC <-> district join, and this resolver becomes the fallback for states the LGD scrape doesn't cover. Status post-2026-05-22: this is now the realised state per [ADR-0033](../decisions/0033-retire-wikipedia-districts-adapter.md) - the lookup is built from entities.json's LGD-keyed district rows; the resolver itself is unchanged.

### ADR-0033 rejected alternatives

Verbatim from the originating ADR. Append-only per parent plan section 9 (keep-receipts).

- **D.1.a - Repoint the wikipedia adapter to write an ephemeral sidecar under `.runtime/`.** Keep `parse_districts()` and `districts_url()` alive; redirect the writer output to `.runtime/wikipedia/districts/<S>.json` (gitignored, ephemeral by [CLAUDE.md section 2](../../../CLAUDE.md)) and consume it from `pipeline/reference.py` only as the district-name lookup input for the constituencies parser. Rejected for three converging reasons: (1) the adapter is a Bootstrap Filter that already finished bootstrapping - Indian districts change at decade-scale via gazette notification, not at adapter-poll-rate, so a "fresh re-scrape on every run" produces nothing that entities.json doesn't already contain authoritatively; (2) the constituencies parser only needs `display_name -> legacy_id` for resolution, and entities.json carries both (the `legacy_id` field was deliberately preserved in Phase A precisely for this case) - going via Wikipedia adds latency, an outbound HTTP dependency, and a parser failure surface for zero new information; (3) splitting "where district identity comes from" between two sources (entities.json for the canonical fields, `.runtime/` scratch for the lookup table) recreates the same provenance-smear class as the 2026-05-16 `fetched_at` lesson.
- **D.1.b - Patch entities.json with a `wikipedia_label_alias` array column to absorb Wikipedia's romanisations.** Keep the adapter alive but make its output land as a new `wikipedia_label_alias: [string]` column on each district entity, populated by an explicit `tools/refresh_district_label_aliases.py` script; the constituencies parser would then resolve against the alias array first, falling back to `display_name`. Rejected: pollutes the citizen-trusted taxonomy with editorial scrape noise. entities.json is the citizen-facing canonical store ([canonical-store.md section 5](../data/canonical-store.md)); every column on it is a citizen contract. "List of romanisations a particular Wikipedia editor used on a particular date for the District column of a particular page" is not a citizen contract - it is parser-internal disambiguation state. The existing two-pass `_strip_parens` + `_norm` skeleton-key resolver already gets 100% on TN (234/234) and KL (140/140) without per-state alias tables; the alias column would solve a problem that does not exist while inviting taxonomy bloat. (OWID precedent per [CLAUDE.md section 0a](../../../CLAUDE.md) "The One Rule": `countries.csv` carries the canonical display name; alternate romanisations are NOT enumerated on the canonical row.)
- **Bootstrap-Filter framing (Gregor) - why we are not preserving the adapter "for symmetry".** In the *Enterprise Integration Patterns* taxonomy this is a textbook Bootstrap Filter: a one-shot pipe whose only job is to seed a downstream canonical store before the canonical store takes over as the source of truth. Bootstrap Filters MUST be deleted once the bootstrap is complete; keeping them alive "in case we need to re-seed" turns them into a Shadow Source - a second writer with subtly different semantics that drifts over time and is invariably wrong by the time you reach for it. The right way to "re-seed" is to update entities.json directly (a typed PR against a typed schema) or to add a new LGD-sourced loader (the long-term canonical path).
- **Make `core/schema_registry.py`'s import-time `schema_id()` call pattern lazy or wrap it in try / except.** Rejected: Phase C audit flagged the module-scope `_schema_id = schema_id("district.schema.json")` call inside `DistrictsCollection` as an "import-time crash risk" because it would have crashed pytest collection if the schema file vanished while the class still existed. The fix in D.1 is NOT to make `schema_id()` lazy - that would defeat the structural fix the registry exists to provide. The fix is to DELETE the class together with the schema-file reference, which restores the invariant "every `schema_id(name)` call has a corresponding `datasets/schemas/<name>` on disk". Per Gregor: import-time `schema_id()` is a contract smell, not a code smell - it correctly fails loud when the contract surface is partially deleted, exactly as designed. Leave the call pattern alone.

## See also

- [Backend overview](overview.md), [Core](core.md), [Pipeline](pipeline.md)
- [ECI source adapter](sources-eci.md) — the canonical source for results data.
- [Constituency hierarchy & status lifecycle](../data-model.md#constituency-hierarchy-and-status-lifecycle)
- [`docs/concepts/electoral-hierarchy.md`](../../concepts/electoral-hierarchy.md)

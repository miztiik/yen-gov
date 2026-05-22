# ADR-0033 — Retire the Wikipedia districts adapter entirely

**Status**: Accepted
**Date**: 2026-05-22
**Deciders**: User (autonomous per the explicit "make good decisions" + "take help of the custom agents" delegation in this session) + Hans (Governance) + Max (Indicator Scout) + Gregor (Architect) — three custom agents consulted in parallel; unanimous recommendation D.1.c.

## Context

T.0c-iii Phase A ([PR #81](https://github.com/miztiik/yen-gov/pull/81), commit `a3d45611`) folded the 145 current districts from the 6 per-state `datasets/reference/in/states/<S>/districts.json` files INTO `datasets/taxonomy/entities.json` as `entity_type='district'` rows. Each district carries `legacy_id` (the 3-letter wikipedia-derived code preserved as the existing `constituencies.json` cross-reference key) and `lgd_code` (the LGD source-of-truth identifier per CLAUDE.md §3 "never invent IDs when an issuing authority publishes one").

Phase B ([PR #82](https://github.com/miztiik/yen-gov/pull/82), commit `2c9d9712`) stripped the `districts.json` loader from `backend/yen_gov/taxonomy/entities_seed.py` and the `emit-taxonomy` CLI no longer walks the per-state directory. The `entities.parquet` SHA-256 stayed `771ECEC3…62243ED` byte-stable across both phases, proving the loader removal had zero data effect.

The original Phase C scope was `git rm` of the 6 data files + `district.schema.json`. A pre-deletion grep audit (per the 2026-05-21 lesson "audit ALL of backend/, tools/, docs/, admin/ before `git rm` of any file under `datasets/`") surfaced 9 live consumers — most importantly an **import-time crash risk**: `backend/yen_gov/core/models.py:152` had `class DistrictsCollection(_Artifact): _schema_id = schema_id("district.schema.json")` at module scope, so deleting the schema file would have crashed every pytest collection across the entire backend. Phase C shipped instead as a docs-only handover ([PR #83](https://github.com/miztiik/yen-gov/pull/83), commit `70bd303e`) scoping a multi-PR Phase D arc.

The remaining wikipedia districts subsystem after Phase B is:

```
backend/yen_gov/sources/wikipedia/districts.py       # ~180 lines, parser + dataclass
backend/yen_gov/sources/wikipedia/urls.py            #   districts_url() function (~4 lines)
backend/yen_gov/core/models.py                       #   DistrictEntry + DistrictsCollection (~25 lines)
backend/yen_gov/pipeline/reference.py                #   districts fetch+parse+write block (~15 lines)
backend/yen_gov/cli.py                               #   "reference" command echoes districts count
backend/tests/test_core_models.py                    #   test_districts_collection_round_trip
backend/tests/test_sources_wikipedia_live.py         #   test_live_districts_tn (live HTTP)
docs/architecture/backend/sources-wikipedia.md       #   district parser section
docs/architecture/data-model.md                      #   "id_source: wikipedia" fallback wording
```

It is a **Bootstrap Filter** (Hohpe, *Enterprise Integration Patterns*): it served exactly one purpose — bootstrap the districts.json files that seeded the canonical taxonomy. With the seeding complete and entities.json now the source of truth, the adapter has **zero downstream consumers**. Its only remaining "output" would be a re-scrape of the same Wikipedia pages whose result is already on disk in a more authoritative form (entities.json's `lgd_code` is what LGD publishes; Wikipedia's "Code" column is editorial).

## Decision

**Retire the wikipedia districts adapter entirely (D.1.c)**: delete `backend/yen_gov/sources/wikipedia/districts.py`, the `districts_url()` builder, the `DistrictEntry` + `DistrictsCollection` Pydantic models, the districts fetch+parse+write block from `pipeline/reference.py`, the "reference" CLI's districts echo, and the two associated tests. Rewrite the constituencies parser's district-name lookup to source `[(display_name, legacy_id), ...]` pairs from `datasets/taxonomy/entities.json` instead of from a freshly-scraped districts.json.

The constituencies parser's two-pass `_strip_parens` + `_norm` heuristic district-name resolver itself is **unchanged**. Only the input lookup dict's source changes — from a parsed `DistrictsCollection` to a filtered `entities.json` projection. The `build_district_lookup()` helper signature stays identical.

Schema-version constants for `district.schema.json` (still on disk pending Phase D.3) are unaffected: `core/schema_registry.py` reads schema metadata lazily, so the deleted `DistrictsCollection` was the only caller — no other code-path references `district.schema.json` from Python.

## Alternatives considered (rejected)

### D.1.a — Repoint the wikipedia adapter to write an ephemeral sidecar under `.runtime/`

Keep `parse_districts()` and `districts_url()` alive; redirect the writer output to `.runtime/wikipedia/districts/<S>.json` (gitignored, ephemeral by CLAUDE.md §2) and consume it from `pipeline/reference.py` only as the district-name lookup input for the constituencies parser.

**Rejected** for three converging reasons:
1. The adapter is a Bootstrap Filter that already finished bootstrapping. There is no recurrence — Indian districts change at decade-scale via gazette notification, not at adapter-poll-rate, so a "fresh re-scrape on every run" produces nothing that entities.json doesn't already contain authoritatively.
2. The constituencies parser only needs `display_name → legacy_id` for resolution. entities.json carries both (the `legacy_id` field was deliberately preserved in Phase A precisely for this case). Going via Wikipedia adds latency, an outbound HTTP dependency, and a parser failure surface for zero new information.
3. Splitting "where district identity comes from" between two sources (entities.json for the canonical fields, .runtime/ scratch for the lookup table) recreates the same provenance-smear class as the 2026-05-16 `fetched_at` lesson — two sources with subtly different update cadences, neither truly authoritative.

### D.1.b — Patch entities.json with a "wikipedia_label_alias" array column to absorb Wikipedia's romanisations

Keep the adapter alive but make its output land as a new `wikipedia_label_alias: [string]` column on each district entity, populated by an explicit `tools/refresh_district_label_aliases.py` script. The constituencies parser would then resolve against the alias array first, falling back to `display_name`.

**Rejected**: pollutes the citizen-trusted taxonomy with editorial scrape noise. entities.json is the citizen-facing canonical store ([§5 of canonical-store.md](../data/canonical-store.md)); every column on it is a citizen contract. "List of romanisations a particular Wikipedia editor used on a particular date for the District column of a particular page" is not a citizen contract — it is parser-internal disambiguation state. The existing two-pass `_strip_parens` + `_norm` skeleton-key resolver already gets 100% on TN (234/234) and KL (140/140) without per-state alias tables; the alias column would solve a problem that does not exist while inviting taxonomy bloat. (See Max's OWID precedent: `countries.csv` carries the canonical display name; alternate romanisations are NOT enumerated on the canonical row.)

### Bootstrap-Filter framing (Gregor) — why we are not preserving the adapter "for symmetry"

In the *Enterprise Integration Patterns* taxonomy this is a textbook Bootstrap Filter: a one-shot pipe whose only job is to seed a downstream canonical store before the canonical store takes over as the source of truth. Bootstrap Filters MUST be deleted once the bootstrap is complete; keeping them alive "in case we need to re-seed" turns them into a Shadow Source — a second writer with subtly different semantics that drifts over time and is invariably wrong by the time you reach for it. The right way to "re-seed" is to update entities.json directly (a typed PR against a typed schema) or to add a new LGD-sourced loader (the long-term canonical path).

### Why we are NOT changing `core/schema_registry.py`'s import-time `schema_id()` call pattern

Phase C audit flagged the module-scope `_schema_id = schema_id("district.schema.json")` call inside `DistrictsCollection` as an "import-time crash risk" because it would have crashed pytest collection if the schema file vanished while the class still existed. The fix in D.1 is **not** to make `schema_id()` lazy or to wrap it in try/except — that would defeat the structural fix the registry exists to provide (see the registry's own docstring re: drift between hand-typed `_schema_version` literals and `x-version` in the schema file). The fix is to **delete the class together with the schema-file reference**, which restores the invariant "every `schema_id(name)` call has a corresponding `datasets/schemas/<name>` on disk". Per Gregor: import-time `schema_id()` is a **contract smell**, not a code smell — it correctly fails loud when the contract surface is partially deleted, exactly as designed. Leave the call pattern alone.

## Consequences

### Wins

- Adapter surface area shrinks by ~250 LoC (parser + URL builder + model + fetch block + tests) with zero behavioural regression: existing `constituencies.json` files are unchanged byte-wise, and a fresh `yen-gov reference <state>` run produces a `constituencies.json` whose `district_id` resolution succeeds for every district that has a `legacy_id` in entities.json.
- One fewer outbound HTTP dependency on a per-state reference run (Wikipedia districts page no longer fetched).
- entities.json becomes the unambiguous source of truth for district identity, matching the Phase A/B fold-in's stated intent.
- Unblocks D.2 (delete `tools/lgd/backfill_lgd_codes.py` — it was writing into the very districts.json files that Phase D.3 will delete) and D.3 (the original `git rm` of the 6 districts.json + district.schema.json).

### Losses

- The Mahe and Yanam UT-sub regions of Puducherry (U07) are not enumerated by LGD as standalone districts, so they are absent from entities.json. ACs in those regions land with `district_id=null` on a fresh `yen-gov reference U07` run. This was already the post-fold-in behaviour (Phase A skipped 2 Mahe/Yanam rows per the missing-`lgd_code` preflight); D.1 surfaces it explicitly in the `_district_lookup_from_entities()` docstring and in [sources-wikipedia.md](../backend/sources-wikipedia.md). Acknowledged structural gap; the eventual fix is either (a) an LGD revision that enumerates UT-sub regions, or (b) a manual override row in entities.json with an issuing-authority-defined identifier. Phase D.3 commit body will document this acknowledgement in full.
- One live test (`test_live_districts_tn`) and one round-trip test (`test_districts_collection_round_trip`) are deleted. Both were exercising adapter code that no longer exists; their parity-of-thought successor is the (existing) `test_live_ac_constituencies_tn` test which round-trips through `constituency.schema.json` and which retains coverage of the entities.json-sourced `district_id` lookup path via the constituencies parser.

### Future work (separate PRs)

- **Phase D.2** — delete `tools/lgd/backfill_lgd_codes.py`. It walked `datasets/reference/in/states/*/districts.json` to add `lgd_code` back; with districts.json being deleted in D.3 and the canonical districts on entities.json already carrying `lgd_code`, the tool has no purpose.
- **Phase D.3** — `git rm` the 6 districts.json files + `district.schema.json` + update 10 doc/plan references + amend `datasets/migration-ledger.csv` row 218 + add the Mahe/Yanam gap acknowledgement to the commit body.

## Links

- Plan: [TODO/20260522-districts-wikipedia-adapter-retirement-handover.md](../../../TODO/20260522-districts-wikipedia-adapter-retirement-handover.md)
- Phase A PR: [#81](https://github.com/miztiik/yen-gov/pull/81) (`a3d45611`)
- Phase B PR: [#82](https://github.com/miztiik/yen-gov/pull/82) (`2c9d9712`)
- Phase C handover PR: [#83](https://github.com/miztiik/yen-gov/pull/83) (`70bd303e`)
- Doctrine: CLAUDE.md §3 (never invent IDs — LGD for districts), §10 (no shadow sources)
- OWID precedent (per CLAUDE.md §0a "The One Rule"): `countries.csv` carries canonical display name; alternate romanisations are NOT enumerated on the canonical row.
- 2026-05-21 lesson: pre-deletion grep audit ALL of backend/, tools/, docs/, admin/ before any `git rm` under `datasets/`.
- 2026-05-16 lesson: provenance-smear class — two sources with different update cadences, neither truly authoritative.

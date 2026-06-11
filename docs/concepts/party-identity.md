# Party identity

**Last Updated**: 2026-06-11

How yen-gov assigns a stable `party_id` to every observation that carries a party reference, and the rules a resolver MUST honour when mapping a publisher-string to that id. This is the identity layer; render colour lives in [party-colour-resolution.md](party-colour-resolution.md); the lineage catalogue lives in [../architecture/data/party-lineage.md](../architecture/data/party-lineage.md).

The single sanctioned resolver entrypoint is [`backend/yen_gov/canonical/party_resolver.py`](../../backend/yen_gov/canonical/party_resolver.py). It replaced the legacy `backend/yen_gov/canonical/adapters/eci/party_lookup.py` in the [PR-1 row](../archive/plans/20260610-electoral-data-quality-and-party-catalogue-plan.md) of the electoral-quality plan (merge SHA `ada00e2d`, 2026-06-10).

## See also

- [../architecture/data/canonical-store.md](../architecture/data/canonical-store.md) - section 5 (Sources schema) names the FK target for every observation row.
- [../architecture/data/party-lineage.md](../architecture/data/party-lineage.md) - the 33-case lineage catalogue (JNP / JD / SHS / NCP / AIADMK / BJS chains).
- [../architecture/backend/validator.md](../architecture/backend/validator.md) - section "Tier C - per-source parity" runs the parity CLI that verifies every party reference resolves.
- [party-colour-resolution.md](party-colour-resolution.md) - what colour the resolved `party_id` renders as.
- [owid-alignment.md](owid-alignment.md) - The One Rule; OWID's `origin.*` model is the precedent for the citation-ledger shape sources rows use.
- [data-provenance.md](data-provenance.md) - ADR-0032 + ADR-0042; provenance is per-row, never per-shard.
- [electoral-hierarchy.md](electoral-hierarchy.md) - AC <-> PC 1:1, AC <-> district 1:M; identity hierarchy is orthogonal.
- [CLAUDE.md](../../CLAUDE.md) - Holy Law #5 (structural fixes only); Holy Law #9 (provenance mandatory); section 10 no-silent-demotion.

## 1. The identity contract

`party_id` is the sole join key. The opaque slug shape is:

```
parties.IN.<UPPER_TOKEN>
```

`<UPPER_TOKEN>` is uppercase ASCII letters, digits, and underscores only. Examples: `parties.IN.BJP`, `parties.IN.INC`, `parties.IN.AITC`, `parties.IN.DMK`, `parties.IN.AIADMK`, `parties.IN.SHS_UBT`, `parties.IN.NCP_SP`, `parties.IN.AIADMK_OPS`. No dots inside `<UPPER_TOKEN>`. No mixed case.

Four invariants the slug honours:

1. **Stable across cycles.** A party's `party_id` does not change when ECI re-issues its registration code, when its short name varies between publishers, when it changes its full name (a `name_history[]` blob records the rename, the id does not move), or when its alliance membership shifts.
2. **Opaque to consumers.** Downstream code never parses `<UPPER_TOKEN>` to infer state, founding date, or ideology. Identity metadata lives in `parties.csv` columns (`recognition_scope`, `home_state_codes`, `founded_year`, etc.); the slug is a join key, not a reference.
3. **PK in `datasets/data/entities/parties.csv`.** Every observation row carrying a party reference (`*_election_results.csv` per-state shards, every `candidacies.csv` under `datasets/elections/`, every `summary.csv`, every `party_alliances.csv`) FKs against `parties.csv.party_id`. The FK closure is enforced by Tier-A `tests/test_party_id_fk_closure.py` and Tier-B `python -m yen_gov validate --root .`.
4. **`short` is display, not identity.** Two parties MAY share a `short` value (e.g. two state-specific outfits both shown as "JP"). `party_id` MUST NOT collide. The citizen UI renders `short`; queries join on `party_id`.

## 2. The 4-class collision taxonomy

When a publisher emits a party reference, four classes of mismatch can prevent a naive equality lookup from finding the right canonical row. The resolver MUST handle each class; the validator MUST detect when one slips through.

| # | Class | Example | Resolver behaviour |
| --- | --- | --- | --- |
| 1 | **Publisher-string-to-canonical** | ECI emits `"ADMK"`; canonical id is `parties.IN.AIADMK` (the alias `ADMK` is registered on the AIADMK row). | Case-insensitive UPPER lookup against the aliases set on `parties.csv`; first hit wins. |
| 2 | **Split-party identity** | Maharashtra 2024: ECI emits `"SHS"` for both Shinde-faction candidates AND UBT-faction candidates. The two factions have distinct canonical ids (`parties.IN.SHS` vs `parties.IN.SHS_UBT`). | Pure short-name match is insufficient. The resolver consumes `eci_code` (the per-vintage numeric registration code) when the publisher provides it; ECI awarded the Shinde faction the original registration symbol, so its `eci_code` resolves to `parties.IN.SHS`. UBT carries a different `eci_code`. Without `eci_code` the resolver MUST surface a curator decision, not guess. |
| 3 | **Alias-vs-short** | TCPD's PoliticalPartiesIndia table abbreviates "All India Anna Dravida Munnetra Kazhagam" as `"AIADMK"` (matching the canonical short); the ECI Statistical Report on the same election emits `"ADMK"` (an alias). Both resolve to `parties.IN.AIADMK` but only if BOTH strings are members of the aliases set. | The aliases column on `parties.csv` carries the union of every label-shape every publisher has emitted historically. New aliases are added via the parity-CLI VERIFIED loop, NEVER hand-edited per individual sighting. |
| 4 | **Sentinel-vs-real** | A publisher row emits `""` (empty), `"IND"` (independent), or `"NOTA"` (none of the above). These are not real parties; they are sentinels. | The resolver detects sentinel inputs BEFORE alias lookup. NOTA -> `parties.IN.NOTA`. Independent flag set -> `parties.IN.IND`. Empty string with no `is_independent`/`is_nota` signal -> `parties.IN.UNK`, with the upstream label preserved on the row's `party_short_raw` column for citizen-UI fallback. **Empty `party_id` is FORBIDDEN** post the electoral-quality plan (Tier-A `test_party_id_fk_closure.py` enforces this strictly). |

The Tier-A test that codifies the contract walks every candidacies + summary + per-state election_results CSV on every `pytest -q` run and asserts every `party_id` is either an FK match in `parties.csv` OR is `parties.IN.UNK` (with `party_short_raw` carrying the upstream label). Empty-string is a fail; a non-sentinel value not in `parties.csv` is a fail. This test caught the TN-2026 AIADMK regression that motivated the entire plan.

## 3. Resolver priority

The resolver applies its rules in strict order; the first hit wins, no fallback combinations are mixed:

1. **NOTA flag** (boolean column on the upstream row, OR the canonical `"NOTA"` short string). Output: `parties.IN.NOTA`.
2. **Independent flag** (boolean column, OR the canonical `"IND"` short string). Output: `parties.IN.IND`.
3. **ECI code** (per-vintage numeric registration code, when the upstream row carries it). Output: the `party_id` whose `eci_codes` pipe-list contains the matching code.
4. **Alias match** (case-insensitive UPPER lookup against the `aliases` set). Output: the `party_id` of the matching row.
5. **Short match** (case-insensitive UPPER lookup against `parties.csv.short`). Output: the `party_id` of the matching row. Short collisions across rows force a STOP-AND-SURFACE; the resolver does not pick arbitrarily.
6. **Fallback**: `parties.IN.UNK`, with the upstream label carried verbatim on the row's `party_short_raw` column. The resolver also raises a `UnknownPartyError` callable by adapter code that wants to fail-loud rather than write a sentinel.

Two derived rules the resolver enforces:

- **No silent demotion** (CLAUDE.md section 10): when an upstream publisher names a real party that the resolver cannot map, the row carries `parties.IN.UNK` AND `party_short_raw = <publisher_label>`. Citizen UI shows the upstream label; the citation never disappears. Auto-correcting `"some unknown short"` to `"BJP"` because it "looks similar" is BANNED.
- **No new mint without sign-off** (Hans verdict, Wave 0 / section 10): when the alias-resolver misses a real party, the engineer adds the new alias to the existing `parties.csv` row (UPSERT). Minting a NEW row in `parties.csv` requires a Hans-approved row in the lineage catalogue ([party-lineage.md](../architecture/data/party-lineage.md)) and travels through the parity-CLI VERIFIED loop.

## 4. Sentinels are first-class

Three rows in `parties.csv` carry `is_sentinel = true`:

| `party_id` | `short` | `full` | `recognition_scope` | Founded |
| --- | --- | --- | --- | --- |
| `parties.IN.UNK` | UNK | Unknown party (resolver fallback) | sentinel | - |
| `parties.IN.IND` | IND | Independent | sentinel | - |
| `parties.IN.NOTA` | NOTA | None Of The Above | sentinel | 2013 |

Sentinels ARE part of FK closure: every candidacies row carrying `parties.IN.IND` MUST resolve against `parties.csv` from the moment PR-0 of the electoral-quality plan landed (merge SHA `9df75919`, 2026-06-10). The previous practice of hardcoding the three strings as inline constants in adapter code was retired; the canonical `SENTINELS` dict in `party_resolver.py` imports the same three slugs by name.

## 5. Schema (parties.csv v1.1, 18 columns)

The parties.csv contract widened from 8 columns to 18 in PR-0 of the electoral-quality plan. The 10 new columns are all `nullable: true`; existing rows remain valid until enriched.

| Column | Purpose |
| --- | --- |
| `party_id` (PK) | Opaque slug `parties.IN.<UPPER>`. |
| `short` | Display label. Two rows MAY share a short value; party_id MUST NOT collide. |
| `full` | Long name as commonly cited. The display-time citation; never used for joins. |
| `eci_codes` | Pipe-list of ECI registration codes the party has carried across vintages. |
| `brand_colour` | OkLCh hex; resolver carries it as a hint, not the render colour (see [party-colour-resolution.md](party-colour-resolution.md)). |
| `symbol_asset` | URL to the citizen-UI symbol render. |
| `wikipedia` | URL to the canonical Wikipedia page. |
| `aliases` | Pipe-list of every label-shape every publisher has emitted (case-insensitive UPPER). The resolver's class-1 + class-3 lookup target. |
| `recognition_scope` | Enum: `national`, `state`, `unrecognised_registered`, `defunct`, `sentinel`. ECI is the authoritative source per Q1 fact-class table. |
| `home_state_codes` | Pipe-list of ISO 3166-2 codes for state-recognised parties. |
| `founded_year` | Integer; matches the lineage-catalogue row when present. |
| `dissolved_year` | Integer; populated only when the party formally dissolved (rare; ECI rarely de-registers). |
| `predecessor_party_ids` | Pipe-list of `parties.IN.<X>` slugs; identifies the lineage row(s) this party descends from. See [party-lineage.md](../architecture/data/party-lineage.md). |
| `successor_party_ids` | Pipe-list of `parties.IN.<X>` slugs; identifies the lineage rows that descend from this party. |
| `name_history` | JSON-blob: `[{"from": "YYYY", "to": "YYYY", "short": "...", "full": "...", "source_id": "..."}]`. Records rebrandings without moving the id. |
| `claims_to_parent_name` | Boolean; true for the ECI-favoured side of a contested split (see Q7 design rationale below). |
| `name_native_script` | Non-Latin name where the publisher emits one; UI policy filters it OUT on the elections surface per the No-Hindi rule. |
| `is_sentinel` | Boolean; true for the 3 sentinel rows above. |

The schema bump from v1.0 to v1.1 is purely additive (Gregor verdict, Wave 0 / section 7). Schema authority: [`datasets/data/_schema/columns.json`](../../datasets/data/_schema/columns.json) `parties.csv` entry; bump receipt in the same file's `x-changelog`.

## 6. Design rationale - identity model for the 2022-2024 ECI-symbol splits (Q7)

The Maharashtra and Tamil Nadu electoral cycles after 2022 forced a choice on how to encode three high-stakes party splits: AIADMK (the 2022 OPS-EPS faction war, then ECI ruling), Shiv Sena (Feb 2023 ECI ruling), and NCP (Feb 2024 ECI ruling). Three options were debated by Hans (Governance) in Wave 0:

- **Option (a) - continuous parent id.** Keep `parties.IN.AIADMK` / `parties.IN.SHS` / `parties.IN.NCP` continuous; ECI ruled the dominant faction retains name + symbol, so from ECI's view no split occurred, only a defection. The competing faction becomes a NEW id. **Rejected** because it conceals the political reality of the split from citizens reading historical charts; the dominant faction's vote share post-split is a different political object from its vote share pre-split.
- **Option (b) - mint child ids on every split.** Parent gets `dissolution_date`; both children carry `predecessor_party_ids = [parent]`. Citizen UI surfaces the break annotation always. **Rejected** because it implies ECI's ruling has no consequence for identity; the ECI-favoured faction loses its registration continuity in our model when in fact it retained the symbol, the registration, and the legal continuity in publisher reality.
- **Option (c) - hybrid (CHOSEN).** Keep the parent id continuous for the ECI-favoured side AND mint a separate id for the breakaway. The continuous side carries `claims_to_parent_name = true`; the breakaway carries its own opaque slug. Trade-off: yen-gov endorses ECI's call on every split, which is acceptable under Holy Law #9 (provenance is mandatory; ECI is the issuing authority on party registration).

Option (c) produces this mapping for the three 2022-2024 splits:

| Faction | `party_id` | `claims_to_parent_name` |
| --- | --- | --- |
| AIADMK (EPS-faction, ECI-favoured Feb 2024) | `parties.IN.AIADMK` | `true` |
| AIADMK (OPS-faction, 2022 split, not ECI-favoured) | `parties.IN.AIADMK_OPS` | `false` |
| AMMK (Sasikala-wing 2018 breakaway, distinct from 2022 OPS faction) | `parties.IN.AMMK` | `false` |
| Shiv Sena (Shinde-faction, ECI-favoured Feb 2023) | `parties.IN.SHS` | `true` |
| Shiv Sena (UBT-faction, Uddhav, 2022 split) | `parties.IN.SHS_UBT` | `false` |
| NCP (Ajit-faction, ECI-favoured Feb 2024) | `parties.IN.NCP` | `true` |
| NCP (Sharad-faction, 2023 split) | `parties.IN.NCP_SP` | `false` |

The `claims_to_parent_name` flag is the citizen-UI hook: a chart spanning the split year MUST surface a break annotation on the breakaway's first appearance ("This party split from `parent-short` in `YYYY`"). The continuous side renders without annotation; the cross-split comparison is still legible because the parent id covers both eras.

User sign-off on option (c): 2026-06-10 (Q7 in plan-doc section 0.3). The decision was applied row-by-row in the PR-S-MH-AE2024 row of the electoral-quality plan (merge SHA `936033f1`).

## 7. What this doc does NOT cover

- **Render colour.** See [party-colour-resolution.md](party-colour-resolution.md). The 3-tier anchor / brand / fallback chain takes `party_id` as input but is decoupled from identity assignment.
- **Lineage graph (predecessor/successor across decades).** See [../architecture/data/party-lineage.md](../architecture/data/party-lineage.md). The 33-case catalogue enumerates the JNP / JD / SHS / NCP / AIADMK / BJS chains and the Hans rule that pre-1980 votes are NEVER backtagged onto modern descendant ids.
- **Alliance modelling.** Alliances are NOT properties of a party; they are event-scoped joins on `party_alliances.csv`. See [`datasets/data/_schema/columns.json`](../../datasets/data/_schema/columns.json) `party_alliances.csv` entry.
- **Recognition flips year-by-year.** The current `recognition_scope` column carries only the LATEST classification. A future v1.2 schema bump will add `recognition_history` as a JSON-blob if a chart needs to render "AAP was a state party until 2024".

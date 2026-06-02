# Party-colour resolution

How yen-gov maps a party row to a render colour. Single sanctioned entrypoint: `frontend/src/lib/colors/resolver.ts`.

## One identity

`party_id` is the sole render-time key. The ECI code is metadata (kept in the row for cross-reference and provenance) but never used as a colour lookup key. Why: a party may swap its ECI code across cycles (re-recognition, splits, mergers) while keeping the same political identity; conversely two distinct parties may briefly share a code during recognition flux. Keying renders on `party_id` (the canonical taxonomy id) keeps colours stable across cycles.

The migration tracker for consumers still on legacy keying lives in [frontend/src/contracts/party-colour-import-allowlist.test.ts](../../frontend/src/contracts/party-colour-import-allowlist.test.ts).

## Resolution chain

`getPartyColor(party_id, row)` walks three tiers in order. The first hit wins; later tiers never override an earlier hit.

| Tier | Source | Hard contract |
| --- | --- | --- |
| 1. Anchor | Hand-curated anchor map keyed by `party_id` | Returns hex as-is; no mutation. Used for the ~15 parties whose colour is a recognisable brand signal (INC, BJP, AAP, TMC, DMK, AIADMK, etc.). |
| 2. Brand | `row.brand_colour` (mirrored from `dim_parties.parquet`) | Returns hex as-is only if `brand_confidence >= 0.6`. Low-confidence brand entries fall through to tier 3 (treated as absent). |
| 3. Fallback | Deterministic hash of `party_id` → palette index | Stable across reloads (pure function of `party_id`). Palette is a fixed 24-colour set tuned for choropleth + stacked-bar legibility. |

## Data flow

```
parties.json  ──►  dim_parties.parquet  ──►  loader (SQL projection)  ──►  row { party_id, brand_colour, brand_confidence, ... }  ──►  resolver  ──►  hex
                       (schema v1.1)              (adapter-elections)             (consumer component)                                      
```

The loader joins `dim_parties` once per query and carries `brand_colour` + `brand_confidence` on every row alongside `party_id`. Consumers never fetch the dim table directly.

## Calling the resolver

### Single cell

```ts
import { getPartyColor } from '$lib/colors/resolver';

const colour = getPartyColor(row.party_id, row);
```

Use for leaf components rendering one cell at a time (a single bar segment, a single chip, a single polygon).

### Batch (palette)

```ts
import { resolvePartyPalette } from '$lib/colors/resolver';

const palette = resolvePartyPalette(party_ids, rows);
// palette is Map<party_id, hex>
```

Use when rendering N elements that share the same set of parties (a stacked-bar series, a choropleth across 234 polygons, an N-column tile board). O(distinct_parties) walks of the chain instead of O(N) per-cell. Functionally identical output.

## Affordance rules

Which canvas may rely on which tier:

| Canvas | Anchor | Brand | Fallback |
| --- | --- | --- | --- |
| Choropleth, stacked-bar, histogram, donut | YES | YES | YES |
| Sankey, swing-flow | YES | YES | YES (but legend MUST disambiguate fallback parties by label) |
| Sparse highlight (1-3 named parties) | YES | YES | NO (use a neutral grey for unnamed parties; never lean on fallback colours for narrative emphasis) |

The fallback tier is legitimate for cross-party comparisons where every party needs a distinguishable hue. The fallback tier is NOT a stand-in for narrative copy.

## Why three tiers (and not one curated map)

- Anchors-only would force a coverage decision for every minor party (~2000 in the taxonomy). Operationally unmaintainable.
- Brand-only would mis-colour 30+ parties whose registered brand colour is either missing, low-confidence, or visually indistinguishable from another party's brand at choropleth scale.
- Fallback-only would re-shuffle colours when the party set changes between elections, breaking visual continuity for the high-recognition parties citizens already associate with a colour.

The 3-tier chain gives high-recognition stability (anchor), broad coverage (brand), and unlimited fallback (hash) in that priority.

## Migration status

5 PRs in the PR-SYM-6 series migrated 4 consumers (`AcStackedBar`, `MarginHistogram`, `StateAcMap`, `RacesBoard`) and the supporting data spine (`dim_parties` schema v1.1 + loader projection). 12 grandfathered consumers remain on the legacy `colors.fill(eci_code, party_short)` path; each is a separate one-PR follow-up gated by its own loader/SQL/data-contract change. The legacy modules (`party-colour.ts`, `anchors.ts`, `store.svelte.ts`, `category-colour.ts`) delete when the ALLOWLIST in the contract test goes empty.

## Recipe to migrate a consumer

1. Verify the loader projection for this consumer already carries `party_id` + `brand_colour` + `brand_confidence` (add if not — that's its own PR).
2. Replace `import { colors } from '$lib/legacy/party-colour'` with `import { getPartyColor } from '$lib/colors/resolver'` (or `resolvePartyPalette` for batch).
3. Replace `colors.fill(eci_code, party_short)` call sites with `getPartyColor(row.party_id, row)`.
4. Remove the consumer's ALLOWLIST entry in `frontend/src/contracts/party-colour-import-allowlist.test.ts`.
5. Run `bun run test --run party-colour-import-allowlist` — must stay green.
6. Visual smoke: load the consumer's page; spot-check 2-3 high-recognition parties keep their colour.

## References

- [TODO/20260527-party-symbol-assets-plan.md](../../TODO/20260527-party-symbol-assets-plan.md) — original plan-doc with one-identity doctrine in §11
- [frontend/src/lib/colors/resolver.ts](../../frontend/src/lib/colors/resolver.ts) — resolver module + module-header contract
- [frontend/src/contracts/party-colour-import-allowlist.test.ts](../../frontend/src/contracts/party-colour-import-allowlist.test.ts) — guardrail + grandfathered-consumer tracker
- [datasets/schemas/dim-parties.schema.json](../../datasets/schemas/dim-parties.schema.json) — dim_parties v1.1 schema

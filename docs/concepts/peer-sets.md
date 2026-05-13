# Peer sets (state tiers)

A *peer set* is a named subset of Indian states/UTs that the catalogue can
declare as the default comparison group for a topic or an artifact. The
canonical taxonomy lives in
[`datasets/reference/in/state-tiers.json`](../../datasets/reference/in/state-tiers.json),
validated against
[`datasets/schemas/state-tiers.schema.json`](../../datasets/schemas/state-tiers.schema.json).

## Why peer sets exist

Cross-state ranking is the most common honesty failure on government
data. Comparing Bihar's per-capita GSDP against Goa's is technically a
number, but politically it's nonsense — Goa is a small consumer-coast
economy, Bihar is a large agrarian one, and they sit in different
fiscal-transfer regimes. The peer-set vocabulary lets the catalogue
say: *for this artifact, the honest peer set is `general_category`* (or
`coastal_states`, or `art_371_states`), and the renderer filters
accordingly.

Two design constraints follow from that brief:

1. **Tiers may overlap.** Sikkim is `general_category` AND `neh` AND
   `himalayan` AND `art_371_states`. Forcing tiers into a partition
   would either drop one of those memberships (silently misleading) or
   invent a 17-tier flat enum (unusable).
2. **Tier identity is what cites it, not the membership set.** `neh`
   (the statutory FC funding window) and `himalayan` (the climate /
   geographic peer set) have near-identical membership today but are
   cited by different policy documents. A future indicator may
   legitimately filter on one but not the other; merging them would
   force either a rename or a re-split later.

## The vocabulary (v1.0)

| Tier id                                    | Kind            | n  | Definition source |
| ------------------------------------------ | --------------- | -- | ----------------- |
| `general_category`                         | residual        | 18 | States not in `special_category` |
| `special_category`                         | statutory       | 11 | NDC 1969 + FC-XII; Art. 275(1) |
| `neh`                                      | statutory       |  8 | NEHC Act 1971 |
| `himalayan`                                | geographic      | 11 | Editorial: Himalayan / trans-Himalayan |
| `ut_legislature`                           | constitutional  |  2 | Art. 239A — Puducherry, J&K |
| `ut_no_legislature`                        | constitutional  |  5 | Art. 239 |
| `nct_delhi`                                | constitutional  |  1 | Art. 239AA — singleton |
| `fc_horizontal_devolution_share_quintile`  | fc_derived      |  0 | FC-XV Annex 5 (recon pending) |
| `coastal_states`                           | geographic      | 13 | Editorial: 7,500-km coastline framing |
| `landlocked_states`                        | geographic      | 23 | Complement of `coastal_states` |
| `art_371_states`                           | constitutional  | 12 | Articles 371 and 371A–371J |

`fc_horizontal_devolution_share_quintile` ships empty in v1.0 — the
per-state shares are tabular and easily mis-transcribed, so the
populated commit will land separately, citing FC-XV Final Report Vol I
Annex 5 directly.

## How catalogue and tiers bind

[`topic-catalogue.json`](../../datasets/reference/in/topic-catalogue.json)
(schema v1.1) declares `peer_set_default` at two levels:

- **Topic level** (`topics[].peer_set_default`): the default for every
  artifact under this topic. Example: the `fiscal` topic defaults to
  `general_category` because comparing fiscal indicators across the
  centre-transfer asymmetry would mislead.
- **Artifact level** (`topics[].artifacts[].peer_set_default`):
  per-artifact override. Example: under `fiscal`, the
  `net_transfers_from_centre` artifact overrides the default to `all`,
  because for *that* indicator the asymmetry **is** the story.

Resolution order: artifact > topic > `"all"` (the no-filter superset).
The frontend helper
[`resolvePeerSetDefault(topic, artifact)`](../../frontend/src/lib/catalogue.ts)
returns a typed `PeerSet`, and
[`resolvePeerSet(file, selector)`](../../frontend/src/lib/state-tiers.ts)
turns that into the actual member list (or `null` for `all`).

Adding a new tier therefore requires three edits:
1. Append to `state-tiers.json` (with sources, definition, members).
2. Broaden the `peer_set_default` enum in `topic-catalogue.schema.json`
   (minor bump, x-changelog entry).
3. Broaden the `PeerSet` union in `frontend/src/lib/catalogue.ts`.

The contract tests in
[`backend/tests/test_datasets_integrity.py`](../../backend/tests/test_datasets_integrity.py)
guard the dataset shape; the unit tests in `state-tiers.test.ts` and
`catalogue.test.ts` guard the resolver.

## What this is *not*

- **Not a partition.** Most tiers overlap. Code that assumes "every
  state is in exactly one tier" is wrong.
- **Not a ranking.** Tiers are categorical labels, not an ordering.
  `art_371_states` is not "above" or "below" `general_category`.
- **Not affirmative action policy.** `special_category` and `neh` reflect
  fiscal-policy windows and statutory bodies as documented; the rendering
  is descriptive, not normative.

## Related documents

- ADR-0022: Topic Front Door + Seventh Schedule list-membership badges
- [`docs/concepts/topic-catalogue.md`](./topic-catalogue.md) (if present)
- CLAUDE.md §15: 4-tier coverage policy (this dataset has unit + contract
  + integration tests; e2e via the topic landing browser smoke once P3.3
  ships)

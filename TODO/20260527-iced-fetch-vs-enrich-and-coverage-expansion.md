# ICED fetch-vs-enrich separation and coverage expansion plan

**Last Updated**: 2026-05-27

**Status**: PROPOSED — awaiting Hans + Max + Gregor sign-off.

**Doc-class**: plan-doc per [ADR-0034](../docs/architecture/decisions/0034-documentation-routing-contract.md). Concept companion: [docs/concepts/ingest-fetch-enrich-separation.md](../docs/concepts/ingest-fetch-enrich-separation.md).

## 0. Mandate

User, 2026-05-27, verbatim:

> "In ICED, we have not ingested all the capabilities or all the data that the iced website publishes. I want to separate the data-fetching process from enrichment into the existing dataset itself (not create a new dataset)."

Audit on `main@352b6da7`: only ~8% of 259 ICED endpoints are ingested today (19 of 259 across the 9 `iced_*` adapters). No explicit fetch-vs-enrich doctrine existed before this plan — adapters mix HTTP + parse + entity resolution + UPSERT in a single module, which is why endpoint coverage has stalled.

## 0bis. Goal

Cover the remaining ~92% (240 of 259) of parameter-free ICED endpoints via the 4-layer pattern from the concept doc. Enrich INTO existing canonical datasets; do NOT create new families or new `indicator_id`s per endpoint.

Param-templated endpoints (119 of 259 require runtime parameters like `state_id`, `fy`, `fuel_type`) are out of scope for this plan-doc; see §"Out of scope" below.

## 0ter. Standing authorizations

Cribbed from [docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md](../docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md) §0ter. Apply to every PR in this plan unless individually overridden:

- Incremental: one phase + one family at a time. No big-bang PRs.
- Own-branch + `git push --force-with-lease` on rebase is acceptable (squash-merge mode discards branch history).
- `gh pr merge --squash --delete-branch` after all 5 DoD gates green per [CLAUDE.md §9](../CLAUDE.md).
- Worker worktrees under `..\yen-gov-iced-<short-tag>` to isolate from master.
- Subagent dispatch optional; default is agent-direct authoring per the grain-rip plan precedent.

## 1. Phases

### Phase F — Fetch sweep (one PR per adapter family)

Bulk-fetch every parameter-free endpoint for each ICED family. Writes raw bytes to `datasets/<family>/_meadow/iced/<vintage>/<endpoint>.json` per [ADR-0041](../docs/architecture/decisions/0041-meadow-tier.md). No parsing, no enrichment.

| PR | Adapter | Endpoints (param-free) |
| --- | --- | --- |
| F.1 | `iced_energy` | ~40 |
| F.2 | `iced_emissions` | ~25 |
| F.3 | `iced_transport` | ~30 |
| F.4 | `iced_buildings` | ~15 |
| F.5 | `iced_industry` | ~20 |
| F.6 | `iced_agriculture` | ~12 |
| F.7 | `iced_waste` | ~8 |
| F.8 | `iced_water` | ~10 |
| F.9 | `iced_macro` | ~5 |

Acceptance per PR: each endpoint produces a deterministic meadow file; rerun is byte-identical; no canonical parquet touched.

### Phase P — Parser sweep (~15 PRs)

Per-endpoint-cluster PRs that convert raw meadow JSONs to typed dicts via per-family `parsers.py`. Pure functions, no I/O. Each parser ships with fixture-based unit tests using the meadow files from Phase F as ground truth.

Cluster sizing: ~10-20 endpoints per PR, grouped by response shape (endpoints that share a JSON envelope can share a parser).

Acceptance per PR: parser returns typed list-of-dicts for every fixture; no canonical write; no entity resolution.

### Phase E — Enrich+Emit (~30-50 PRs, one per indicator UPSERT)

For each endpoint whose parsed rows map to a concept already in canonical, write the `ingest.py` enricher and UPSERT into the EXISTING family parquet.

Per-PR rules (from concept doc):

- Run `python -m yen_gov check-overlap` for every new concept the endpoint claims to introduce.
- If overlap >= 0.70 with an existing `indicator_id`, UPSERT into that id (new vintage row) or add a facet — NEVER mint.
- If overlap < 0.70, only THEN add a `concepts.json` row + mint a new `indicator_id` + cite the dimension that distinguishes it.
- Writer PK `(entity_id, year, period_label, indicator_id)` is the UPSERT key; row count on the target parquet MUST monotonically increase.

Estimated PR count: 30-50 depending on how many ICED endpoints duplicate existing concepts (UPSERT-only) vs introduce genuinely new concepts (mint + UPSERT).

### Phase G — Guardrails

Two NEW guardrails ship as part of this plan, alongside the Phase F/P/E PRs:

- **G.1 Tier-B `tier_b_no_new_parquet_per_endpoint`** (LIVE post-PR-G.1): assert no PR under this plan adds a new `datasets/<family>/<family>_<endpoint>.parquet` stem. UPSERT into existing stems only. Failure mode is hard: PR cannot merge.
- **G.2 Contract test `canonical_upsert_monotonic`** (LIVE post-PR-G.2): after each Phase-E PR, the touched canonical parquet row count must be strictly greater than the pre-PR count. Proves UPSERT semantics (no overwrite, no truncation).

## 2. Out of scope

- **Param-templated endpoints** (119 of 259): endpoints that require runtime parameters (`state_id`, `fy`, `fuel_type`, etc.) need a parameter-enumeration strategy + a separate fetch loop. Tracked in a follow-up plan-doc once Phase F/P/E close on the parameter-free set.
- **Non-ICED publishers**: this plan is ICED-specific. The 4-layer doctrine generalises to any HTTP source, but other publishers (RBI, CEA, NDLM, ECI) get their own plan-docs.
- **Renderer / topic-page placement**: this plan ships canonical data only. Citizen-surface placement (topic-page mounting, descriptor authoring) follows the existing IA plan cadence.

## 3. Estimated effort

- **PR count**: ~50-75 total (9 F + ~15 P + ~30-50 E + 2 G).
- **Wall-clock**: 1-2 months at 5 PRs/day sustained velocity.
- **Risk**: low for Phase F (pure I/O, no semantics); medium for Phase E (concept-overlap calls require Hans + Max review per [CLAUDE.md §0a](../CLAUDE.md)).

## 4. Open questions

- Confirm the 259-endpoint count and the param-free / param-templated split with a fresh ICED portal recon (last recon: 2026-05-11).
- Confirm Phase G.1 + G.2 wiring plan with Gregor before authoring.

## 5. See also

- [docs/concepts/ingest-fetch-enrich-separation.md](../docs/concepts/ingest-fetch-enrich-separation.md) — the doctrine
- [docs/concepts/meadow-tier.md](../docs/concepts/meadow-tier.md) — backend-internal staging
- [docs/architecture/data/canonical-store.md](../docs/architecture/data/canonical-store.md) — writer PK + family parquet
- [TODO/_TEMPLATE-ingest-handover.md](_TEMPLATE-ingest-handover.md) — per-endpoint handover-doc template
- [docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md](../docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md) — concept-overlap rule + standing authorizations precedent
- [ADR-0041](../docs/architecture/decisions/0041-meadow-tier.md) — meadow tier
- [ADR-0044](../docs/architecture/decisions/0044-grain-over-entity.md) — grain-over-entity

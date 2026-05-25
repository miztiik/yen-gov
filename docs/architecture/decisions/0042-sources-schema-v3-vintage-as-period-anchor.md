# ADR-0042: Sources schema v3.0 — vintage as strongest period anchor available

**Last Updated**: 2026-05-26
**Status**: Accepted
**Deciders**: User (autonomous mandate, 2026-05-26) + Gregor (Architect) + Fowler (Engineering) — parallel custom-agent consult 2026-05-26; both converged. Authority assignment per CLAUDE.md §0a: data shape = Gregor (canonical data model) with Fowler underwriting commit shape (Tidy-First, smallest reversible steps).
**Supersedes**: [ADR-0032](0032-sources-citation-ledger.md) v2.0 on vintage semantics only. ADR-0032's body (citation-ledger pivot, 11-column shape, identity-as-citation-triple rationale) is preserved as the v2.0 historical record; the Status pointer at the top of -0032 redirects readers here for current vintage semantics.
**Refines**: [ADR-0041](0041-meadow-tier.md) §non-negotiable #4 ("Vintage in meadow path MUST match `vintage` field of the citation row the `source_id` FK resolves to"). The invariant text in ADR-0041 stays as-is; this ADR resolves the semantic ambiguity that previously made #4 structurally unenforceable for unvintaged publishers.
**Plan reference**: [`TODO/20260517-canonical-long-format-pivot.md` §0e.8a P.1 Energy — sources.parquet vintage backfill + Tier-B vintage check](../../../TODO/20260517-canonical-long-format-pivot.md)

## Context

### What this resolves

[ADR-0032](0032-sources-citation-ledger.md) (sources v2.0, 2026-05-20) defined `vintage` as "OWID origin.vintage verbatim — source's OWN period / revision / edition label" and permitted empty string when the source publishes no vintage. [`energy_sources_seed.py`](../../../backend/yen_gov/canonical/energy_sources_seed.py) ratified that interpretation: 5 NITI ICED rows ship with `vintage = ""` because the ICED APIs are continuously-updated and carry no publisher edition tag; 7 RBI/CEA rows ship with `vintage = "2024-25"` (or `"2026-03"`) because those upstreams DO publish edition tags.

[ADR-0041](0041-meadow-tier.md) (meadow tier, 2026-05-25) then established `datasets/<family>/_meadow/<source>/<vintage>/<file>.json` as the canonical-input contract path. The `<vintage>` segment is operator-chosen and encodes "when did we snapshot this." For ICED meadow files it is `2024-25` (the FY in which the operator ingested). For RBI/CEA meadow files it is `2024-25` / `2026-03` (which happens to equal the publisher tag).

ADR-0041 §non-negotiable #4 says: "Vintage in meadow path MUST match `vintage` field of citation row the `source_id` FK resolves to." With ICED rows carrying `vintage = ""` in the citation ledger but `_meadow/iced/2024-25/` on disk, the invariant is structurally unsatisfiable — `"" ≠ "2024-25"`. PR-A (#265) renamed the Tier-B fence file to `meadow-shard-contract.txt` but left this invariant unenforceable; any Tier-B validator implementing #4 strictly would fail-closed on every ICED meadow file.

### Three options surfaced (2026-05-26 dual-subagent verdict)

- **α** — Redefine `vintage` as "operator snapshot window" everywhere. Hash signature unchanged 3-arg. ICED rows' `vintage` flips `""` → `"2024-25"`; RBI/CEA rows unchanged. 5 source_ids re-hash. Observation FKs re-emit. `indicators.json` baked hashes regenerate. ADR-0032 §vintage amended in place.
- **β** — Relax non-negotiable #4: meadow path vintage MUST equal source vintage OR source vintage MUST be empty (wildcard). Tier-B rule encodes the wildcard. Zero source_id churn.
- **γ** — Schema split: add new field `snapshot_vintage` (extrinsic, equals meadow path); rename existing `vintage` to `publisher_vintage` (intrinsic). `derive_source_id` continues to hash `(producer, title, publisher_vintage)`. Tier-B rule checks `snapshot_vintage = meadow path vintage`. ADR-0041 §nn4 amended to point at `snapshot_vintage`.

### Why β rejected

A rule with a wildcard escape is no rule. The Tier-B fence becomes ceremony — every Phase 2 P.2+ family contributor will hit "my source is unvintaged, the wildcard saves me, why does the rule even exist?" The fence's purpose is to make ADR-0041's §nn4 non-negotiability MEAN something at validate time. Adding a wildcard at the schema layer compromises the invariant at the only layer where it can be machine-checked. Fowler-tagged this as "empty-string-as-magic-value band-aid"; Gregor-tagged it as "Holy Law #5 violation — when the rule says NEVER, it must mean never."

### Why γ rejected

`snapshot_vintage` exists only because filesystem layout exists. The meadow path component IS the snapshot vintage. Putting it on the citation row duplicates filesystem state into the citation ledger — a control-plane concern leaking into the citizen-facing data contract. The schema split creates a second column to mirror state the operator already owns. When ICED is re-snapshotted next FY (paths become `_meadow/iced/2025-26/`), γ requires the operator to author NEW source rows with NEW `snapshot_vintage` AND `publisher_vintage = ""` (still empty). Both rows have the same `publisher_vintage = ""` → identity hash collision on `(producer, title, publisher_vintage)`. The 4-arg hash fix-up Gregor surfaced (`(producer, title, publisher_vintage, snapshot_vintage)`) ripples the identity contract change across every Phase 2 source and re-introduces the very migration cost γ was supposed to avoid. Gregor-tagged this as "speculative generality wearing architectural-purity clothing."

### Why α refined as δ — and ratified as the v3.0 semantics

Gregor's framing: `vintage` = "strongest period anchor available." For publisher-tagged upstreams (RBI Handbook, NFHS, CEA Monthly): publisher edition tag. For continuously-updated APIs (ICED, govt-of-india data portal endpoints): operator snapshot window matching the meadow path. The 3-arg hash signature stays. For the CURRENT dataset this produces values identical to Fowler's plain-α ("vintage is always operator snapshot window") — but the δ framing scales to non-energy families where RBI's `"2024-25"` is genuinely an edition-tag and NOT a snapshot-window decision.

### "The One Rule" (CLAUDE.md §0a) — OWID precedent

OWID's `origin.vintage` is documented as "the year, month, or other label representing the version of the data." OWID does NOT prescribe what to do when the publisher publishes no vintage; in practice, OWID curators fill it with the operator's best guess at a period anchor (date_accessed-derived for continuously-updated sources, edition tag otherwise). δ is consistent with OWID practice — it just makes the rule explicit.

## Decision

`datasets/schemas/source.schema.json` ships as **v3.0**. The `vintage` field's description is rewritten to "strongest period anchor available — publisher edition when the upstream publishes one; operator snapshot window when not." `minLength: 1` is added. The 5 NITI ICED rows in [`energy_sources_seed.py`](../../../backend/yen_gov/canonical/energy_sources_seed.py) flip vintage `""` → `"2024-25"`. The 7 RBI/CEA rows are unchanged. `derive_source_id` keeps its 3-arg signature.

### Migration (5 source_ids churn; rest stable)

| Nickname | Producer | Title | OLD source_id | NEW source_id |
| --- | --- | --- | --- | --- |
| `iced_capacity_metatable` | NITI Aayog India Climate & Energy Dashboard | Capacity Metatable API (state-wise installed capacity, by fuel) | `src-ba5c6fa6acfe` | `src-1240f07df0ac` |
| `iced_deep_dive` | NITI Aayog India Climate & Energy Dashboard | State-wise Deep Dive API | `src-be6a6d5d6493` | `src-bb1d7bec8b34` |
| `iced_gen_metatable` | NITI Aayog India Climate & Energy Dashboard | Generation Metatable API (state-wise electricity generation, by fuel) | `src-b60ed70f19d8` | `src-ddbfadd51428` |
| `iced_distribution_perf` | NITI Aayog India Climate & Energy Dashboard | Distribution Operational Performance API (state-wise billing efficiency, collection efficiency, T&D losses) | `src-cead8f51df6f` | `src-650b1c25d1f7` |
| `iced_distribution_rpo` | NITI Aayog India Climate & Energy Dashboard | Distribution RPO Compliance API (state-wise Renewable Purchase Obligation compliance, by segment) | `src-ca061b1b0adf` | `src-0ea63ed47704` |

CEA `cea_monthly_ic` (`src-` for vintage="2026-03") and 6 RBI rows (`src-` for vintage="2024-25") are byte-identical pre/post — they already carried publisher-edition `vintage` values.

### What changes structurally vs behaviourally

**Structural (Commit 1 of PR-B-revised — gates green out of the box):**

1. `datasets/schemas/source.schema.json` — bump `x-version` to `"3.0"`, add `x-changelog[2]`, rewrite `vintage.description`, add `minLength: 1`.
2. `backend/yen_gov/canonical/citation.py` — `derive_source_id` + `render_citation` docstrings updated to reflect v3.0 semantics. No code-path changes.
3. `backend/yen_gov/canonical/envelope.py` — `SourceRow.vintage` type annotation gets `Field(min_length=1, description=...)`; docstring on `SourceRow` updated.
4. `docs/architecture/decisions/0032-sources-citation-ledger.md` — Status pointer at top: "Superseded on vintage semantics by ADR-0042 on 2026-05-26"; body preserved verbatim.
5. NEW `docs/architecture/decisions/0042-sources-schema-v3-vintage-as-period-anchor.md` (this file).
6. `docs/architecture/decisions/README.md` — register ADR-0042.
7. `docs/concepts/data-provenance.md` — vintage definition section updated.

**Behavioural (Commit 2 of PR-B-revised — atomic; suite green at boundary):**

1. `backend/yen_gov/canonical/energy_sources_seed.py` — 5 ICED `_TRIPLES` entries: vintage `""` → `"2024-25"`.
2. `backend/yen_gov/canonical/adapters/energy/_shared.py` — `ENERGY_SOURCE_ID_BY_NICKNAME` baked-id constants updated (5 churn).
3. `backend/tests/test_energy_sources_seed.py` — expected source_ids updated.
4. `backend/tests/test_energy_sources_fk_closure.py` — expected source_ids updated.
5. `backend/tests/test_energy_installed_capacity_parity.py` — `src-be6a6d5d6493` references updated.
6. `backend/tests/test_energy_distribution_parity.py` — `src-cead8f51df6f` reference updated.
7. `backend/yen_gov/canonical/adapters/energy/demand_supply.py:102` — comment updated.
8. `datasets/taxonomy/sources.parquet` — regenerated via `emit-taxonomy` (5 rows update; 7 stable).
9. `datasets/taxonomy/indicators.json` — 5 baked source-id strings search-replaced.
10. `datasets/taxonomy/indicators.parquet` — regenerated by `emit-taxonomy`.
11. `datasets/energy/*.parquet` — re-emitted via canonical writer; observation FKs now reference new source_ids.

**Structural (Commit 3 of PR-B-revised — Tier-B rule):**

1. `backend/yen_gov/validate.py` — NEW `tier_b_meadow_vintage_matches_source_id(root)` rule. Walks `datasets/<family>/_meadow/<source>/<vintage>/*.json`; derives `(source, vintage)` from path; checks `sources.parquet` has ≥1 row with matching `source_short_name` → `producer` mapping AND `vintage = <path-vintage>`. No wildcards. Wired into `run()`.
2. `backend/tests/test_validate.py` — positive + negative tests for the new rule.

## Rationale

The 3 candidates split on different axes of correctness:

| Axis | α (δ) | β | γ |
| --- | :-: | :-: | :-: |
| Tier-B fence is enforceable invariant | ✓ | wildcard | ✓ |
| ADR-0041 §nn4 stays as-is | ✓ | edit | edit |
| Identity contract (3-arg hash) preserved | ✓ | ✓ | breaks |
| Sources schema simplicity (no field duplication) | ✓ | ✓ | adds field |
| Citation ledger free of operator-state | ✓ | ✓ | mixes |
| Scales to Phase 2 P.2+ without per-family debate | ✓ | ✗ | ✓ |
| Re-emit cost (5 source_ids re-hash) | yes | no | yes |

δ is the only option that wins on every axis except re-emit cost, and the re-emit cost is one-time and bounded (the canonical writer's UPSERT semantics + `emit-taxonomy`'s hash-regen path already exist). The user mandate (2026-05-26) explicitly accepted re-emit cost in exchange for clean future semantics: "no worries about breaking the past — since we have the data, we should be able to massage it to new schema."

## Rejected Alternatives

### Rejected α-as-stated (Fowler's plain phrasing): `vintage` = "operator snapshot window" always

Fowler's initial framing dropped the publisher-edition concept entirely. **Rejected** because RBI Handbook genuinely DOES publish a "2024-25" edition tag and that's a different epistemic fact from "we snapshotted in 2024-25." For the current dataset both phrasings produce the same string values, but δ's framing preserves the OWID semantic (publisher tag when published) and scales to families where the publisher edition matters for citation precision (NFHS-5 vs NFHS-4 is a publisher-edition distinction; if it ever flipped to operator-snapshot semantics, two NFHS-5 snapshots in different operator-FYs would collide on the same source_id — wrong).

### Rejected β: wildcard relaxation of ADR-0041 §nn4

A Tier-B rule with a wildcard escape is computationally tautological. The fence's existence requires uniform enforcement. (Detailed reasoning above.)

### Rejected γ: `publisher_vintage` + `snapshot_vintage` schema split

Duplicates filesystem state into the citation ledger; collapses on re-snapshot of unvintaged sources. (Detailed reasoning above.)

### Rejected δ′: 4-arg hash `(producer, title, publisher_vintage, snapshot_vintage)`

Considered as a fix-up for γ's identity collision. **Rejected** because it ripples the identity contract change across every Phase 2 source (not just energy ICED), making PR-B blast-radius cover the entire citation ledger. The 3-arg hash is part of the Holy Law #9 surface; changing the arity is a Level-5 contract change with cross-family implications. δ achieves the same outcome with the 3-arg hash intact.

### Rejected ε: defer the entire question; ship Tier-B rule WITHOUT addressing the ICED case

Mark ICED meadow files exempt from Tier-B; ship the rule for CEA/RBI only. **Rejected** because the exemption list becomes a soft allowlist that grows — every future continuously-updated source asks "can I be exempt too?" The exception eats the rule.

## Consequences

### Wins

- **ADR-0041 §nn4 becomes structurally enforceable** as a strict equality check with zero wildcards.
- **Tier-B rule `tier_b_meadow_vintage_matches_source_id` ships in PR-B Commit 3** as a regression guard, not a runtime fix.
- **3-arg identity contract preserved** — Holy Law #9 surface untouched.
- **Schema stays 11 columns** — no `snapshot_vintage` duplication of filesystem state.
- **Citation ledger stays free of operator-mutability** — `vintage` per-row still represents what the citizen would write in a bibliography, just with a sharpened rule for what to write when the publisher gives no tag.
- **Re-snapshot of ICED next FY** produces NEW source rows with `vintage = "2025-26"` and NEW source_ids; no collision with FY24-25 rows.
- **5 publisher-edition rows (RBI/CEA) byte-identical pre/post** — zero churn on the publisher-tagged path.

### Costs

- **5 NITI ICED source_ids re-hash; ~70 observation FK rows in `energy_*.parquet` re-emit; ~28 baked-hash references in `indicators.json` search-replace; 4 backend test files updated.** Mitigated by the canonical writer's existing UPSERT determinism + `emit-taxonomy`'s hash-regen path; total work in one atomic commit.
- **PR-B-revised is 3 commits instead of the planned 1.** Mitigated by Fowler's Tidy-First decomposition: Commit 1 (structural) and Commit 3 (structural) are gating-green-out-of-box; only Commit 2 needs the full re-emit cycle.
- **ADR-0032 §vintage description is now historically inaccurate without the supersession pointer** read first. Mitigated by the Status pointer + `Last Updated` discipline.

### Forward compatibility

- Future schema bumps to v3.x add fields (e.g. v3.1 adds optional `subtitle`) per the established `x-changelog` rules in CLAUDE.md §11.
- Breaking changes (v3.x → v4.0) require a new ADR.
- Phase 2 P.2+ families authoring NEW sources MUST follow δ: pick the publisher edition tag if one exists; otherwise pick the operator snapshot window that matches the meadow path.

## References

- **[ADR-0032](0032-sources-citation-ledger.md)** — sources v2.0 citation ledger (supersedes on vintage semantics)
- **[ADR-0041](0041-meadow-tier.md) §non-negotiable #4** — meadow path vintage must match source vintage (now structurally enforceable)
- **CLAUDE.md §0a** — "The One Rule" (OWID precedent)
- **CLAUDE.md §10** — Anti-patterns; §11 schema versioning + `x-changelog`
- **[`backend/yen_gov/canonical/citation.py`](../../../backend/yen_gov/canonical/citation.py)** — `derive_source_id` (signature unchanged)
- **[`backend/yen_gov/canonical/energy_sources_seed.py`](../../../backend/yen_gov/canonical/energy_sources_seed.py)** — 5 ICED triples flip in PR-B Commit 2
- **[`backend/yen_gov/validate.py`](../../../backend/yen_gov/validate.py)** — `tier_b_meadow_vintage_matches_source_id` lands in PR-B Commit 3
- **[`TODO/20260517-canonical-long-format-pivot.md` §0e.8a](../../../TODO/20260517-canonical-long-format-pivot.md)** — PR-B scope ratification
- **`/memories/lessons.md` 2026-05-25** — strangler-fig blast-radius trap (informed PR-B's autonomous-execution discipline)

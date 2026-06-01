# ADR-0049: Canonical AC join key = lgd_ac_id; eci_no demoted to display label; crosswalk as Canonical Data Model

**Last Updated**: 2026-06-01
**Status**: accepted
**Deciders**: User (big-bang sign-off, supersedes per CLAUDE.md section 0a), Gregor (contract + Strategy-D-hardened verdict), Hans + Max (data-shape), Jony + Citizen (URL grammar)

## Context

Assembly Constituency identity in yen-gov has two spines. Boundary shards key on `lgd_ac_id` (the LGD numeric Assembly Constituency code) per the LGD-golden doctrine ([docs/concepts/admin-level-sourcing.md](../../concepts/admin-level-sourcing.md)), while election-results parquets, indicator-family tables, SoT `constituencies.json` files, and the frontend boundary<->data join still key on `eci_no` (ECI's per-state 1..N ballot enumeration). Every cross-cut pays a name-based translation cost, and no national AC-level indicator can adopt a single primary key.

The R1 audit ([notes/20260601-eci-to-acid-migration-surface-audit.md](../../../notes/20260601-eci-to-acid-migration-surface-audit.md)) mapped ~95 files / ~260 references across 8 surfaces. A direct boundary-file inspection on 2026-06-01 corrected an earlier framing: **30 of 31 AC partitions already carry the LGD code** in feature properties as `AC_ID` (2-digit `State_LGD` + 3-digit `ac_no`, globally unique). Only **U08 (J&K)** genuinely lacks it (post-2022 delimitation, `seat_id` only). The SoT JSON 0% coverage is true but misleading: the LGD data lives in the boundary shards, not the SoT files. The real gap is a single binding table, not external sourcing.

ADR-0044 (grain-over-entity) keeps `entity_id` (`IN-<state>-AC-<delim>-<eci_no>`) as the fact-grain PK; this ADR does not reopen it.

## Decision

Adopt **Strategy-D-hardened**: `lgd_ac_id` becomes the canonical INTERNAL join key; `eci_no` is demoted from identity to the citizen-facing display + URL label.

1. **Crosswalk as one Canonical Data Model.** `datasets/taxonomy/ac_crosswalk.parquet` (schema [ac-crosswalk.schema.json](../../../datasets/schemas/ac-crosswalk.schema.json)) holds one row per `(state_code, eci_no)`, total over every SoT AC, binding it to `lgd_ac_id` (nullable) plus `ac_id`, `ac_name`, `delim_year`, `match_method`, `source_id`.
2. **entity_id stays PK.** ADR-0044 untouched. `lgd_ac_id` is a nullable join attribute, not a new identity.
3. **Harvest-then-fill.** The crosswalk is harvested from existing boundary `AC_ID` provenance for the ~30 covered states (`match_method` = `lgd_direct` where ECI and LGD numbering coincide, `name_reservation_join` where they diverge). U08 and any unresolved AC get `lgd_ac_id = null, match_method = unmapped` and ride `ac_no`/`eci_no` until filled.
4. **Bijection-and-completeness invariant.** A single contract test ([ac_crosswalk.assert_bijection](../../../backend/yen_gov/canonical/ac_crosswalk.py)) is the migration's load-bearing safety net: PK totality, `lgd_ac_id` global uniqueness, strict bijection on the covered subset, and `lgd_ac_id IS NULL` iff `match_method = unmapped`.
5. **Reader-before-writer cutover.** Per ADR-0047, consumers adopt the crosswalk join before any default flips; behavioural cutover rows carry a result-parity oracle.
6. **URL grammar.** The AC route becomes `/s/<state-slug>/ac/<eci_no>-<name-slug>` (e.g. `/s/tamil-nadu/ac/42-tekkali`). `eci_no` stays the leading parse key; the name slug is decorative + parse-tolerant. `lgd_ac_id` is INTERNAL-ONLY and never appears in a URL.

## Consequences

- One join surface replaces scattered name-based `ac_no <-> eci_no` translation; the legacy `apply_ac_no_rewrite_by_name` seam can be retired once coverage is effectively 100% `lgd_direct`.
- A national AC-level indicator can key on `lgd_ac_id` directly.
- Citizens keep the ballot number they recognize in the URL, now with a readable name suffix.
- The migration is far smaller than first framed: ~30 states are harvestable with no external sourcing; only U08/J&K needs data work.
- Provenance: every `lgd_ac_id` binding carries a `source_id` FK to `datasets/taxonomy/sources.parquet`.

## Alternatives considered

### A. Big-bang corpus rewrite to lgd_ac_id everywhere (drop eci_no)

Rejected. Discards the ballot number citizens recognize and forces every results/indicator parquet to rewrite at once with no parity net. The crosswalk gives the same internal benefit incrementally.

### B. Dual-key co-existence with a permanent adapter layer

Rejected. Leaves both spines live forever; the translation cost this ADR removes would persist. The crosswalk is the adapter, but with an explicit retirement path (Row D1).

### C. Keep eci_no as the internal key; treat lgd as display

Rejected. `eci_no` is per-state, not globally unique, and cannot key a national AC table. The LGD code already is globally unique and already present in 30/31 boundary shards.

### D. lgd_ac_id in the URL

Rejected by user. The opaque registry integer (e.g. 33042) is not citizen-legible; the ballot number + name slug is. `lgd_ac_id` stays internal-only.

## See also

- [ADR-0044](0044-grain-over-entity.md) (entity_id stays the fact-grain PK)
- [ADR-0047](0047-schema-version-compatibility-contract.md) (reader-before-writer cutover)
- [docs/concepts/admin-level-sourcing.md](../../concepts/admin-level-sourcing.md) (LGD-golden doctrine)
- [TODO/20260530-eci-to-lgd-acid-migration-plan.md](../../../TODO/20260530-eci-to-lgd-acid-migration-plan.md) (migration plan, Rows A1-D1)
- [notes/20260601-eci-to-acid-migration-surface-audit.md](../../../notes/20260601-eci-to-acid-migration-surface-audit.md) (R1 surface audit)

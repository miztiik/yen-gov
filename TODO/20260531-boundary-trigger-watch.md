# Boundary trigger-watch backlog

**Last Updated**: 2026-05-31

**Status**: PASSIVE. No row is executable today. Each entry waits on an explicit upstream release OR a citizen-facing indicator that demands the corresponding grain.

**Predecessors (archived; consult only for historical context)**:

- [docs/archive/plans/20260529-boundary-rip-and-replace-plan.md](../docs/archive/plans/20260529-boundary-rip-and-replace-plan.md)
- [docs/archive/plans/20260530-boundary-followups-execution-plan.md](../docs/archive/plans/20260530-boundary-followups-execution-plan.md)
- [docs/archive/plans/20260530-boundary-plan-followups.md](../docs/archive/plans/20260530-boundary-plan-followups.md)

**Knowledge already distilled** (do NOT re-derive — read these instead):

- [docs/concepts/admin-level-sourcing.md](../docs/concepts/admin-level-sourcing.md) — 3-convention property-name rule + LGD/Bhuvan/ramSeraph lineage + per-level partition shapes + known coverage gaps (U09, S03).
- [docs/concepts/boundary-data-philosophy.md](../docs/concepts/boundary-data-philosophy.md) — polygon-over-raster + LGD-golden discipline.
- [docs/how-to/add-new-boundary-layer.md](../docs/how-to/add-new-boundary-layer.md) — orchestrator authoring pattern; when to fork vs consolidate.
- [docs/how-to/digitize-ac-from-pdf.md](../docs/how-to/digitize-ac-from-pdf.md) — 4-tier fallback ladder + QGIS workflow (for future delim-PDF states).
- [docs/architecture/decisions/0031-boundary-geometry-strategy.md](../docs/architecture/decisions/0031-boundary-geometry-strategy.md) — one-source-per-level + parallel orchestrators.
- [docs/architecture/decisions/0041-meadow-tier.md](../docs/architecture/decisions/0041-meadow-tier.md) — indicator-family `_meadow/` ingest vs `datasets/boundaries/`.

---

## How to use this file

1. **Do not pre-empt a row.** No row activates without its named trigger.
2. When a trigger fires, lift the row into a fresh focused plan-doc; do NOT execute from this file directly.
3. Mark a row CLOSED here only when (a) its trigger fires AND (b) the resulting PR ships, OR when the row is explicitly abandoned by user mandate.
4. Annual review: re-confirm each trigger still makes sense; collapse rows whose triggers have become impossible (e.g. upstream permanently shuttered).

---

## Backlog (17 rows)

| Row | Title | Trigger | Effort | Value | Source |
| --- | --- | --- | --- | --- | --- |
| B1 | C.2.d Bhuvan panchayat gap-fill (9 states/UTs: HP, J&K, Sikkim, ME, MZ, MN, NL, AR + 1 UT) | PRR / MGNREGS / PRI-funds indicator at panchayat grain | M | MED | C.2.d |
| B2 | C.3.d Urban ward gap-fill (WB-AMRUT + Shillong-CMD + LivingAtlas; 7 states) | Urban-governance / Swachh-Survekshan / AMRUT indicator at ward grain | M per source | MED | C.3.d |
| B3 | C.4 other 7-state villages gap-fill (HP, Sikkim, ME, MZ, MN, NL, AR) | Per-state upstream availability + village-grain citizen indicator | S per state | LOW | C.4 |
| B4 | C.2.c Panchayat district-picker Svelte component | Measured panchayat data + first panchayat-grain indicator | M | MED | C.2.c |
| B5 | C.3.c ULB ward-picker Svelte component | Measured ward data + first ward-grain indicator | M | MED | C.3.c |
| B6 | Frontend villages registry + picker (`VILLAGE_BOUNDARY_BY_DISTRICT` in sources.ts) | First village-grain citizen indicator (MGNREGA person-days / PMGSY / micro-watershed) | M | BLOCKED | Cat 3 |
| B7 | Historical districts (1941-2001, 8 decadal snapshots) | Explicit historical-district indicator demand | L | LOW | Cat 4 |
| B8 | Census 2011 polygon snapshot | Census-grain historical indicator | M | LOW | Cat 4 |
| B9 | SHRUG Census 2011 harmonized variant | Same as B8 | M | LOW | Cat 4 |
| B10 | Habitations / sub-village granularity | Sub-village indicator (unlikely) | XL | LOW | Cat 4 |
| B11 | Polling stations (7 ramSeraph sources) | `/e/` event-page polling-station drill-down | L | MED | Cat 4 |
| B12 | Slums (8 sources: WB-AMRUT, GHMC, Telangana, TN, BBMP, MCGM, Delhi-GSDL, others) | Slum-welfare / urban-health indicator | L per source | MED | Cat 4 |
| B13 | ULB cadastrals (52 ramSeraph sources) | Property-tax / municipal-revenue indicator | XL | LOW | Cat 4 |
| B14 | Post Offices / PostalGIS | Postal-service indicator | S | LOW | Cat 4 |
| B15 | Cadastrals / water / transport / power / buildings / industries / floods / DEM / lithology / SOI topo / lineament | Family-specific indicator adoption (per ADR-0041 `_meadow/` ingest) | M per layer | family-dependent | Cat 4 |
| B16 | Multi-source villages consolidation refactor (`lift_villages_*` -> `--source` flag) | 2nd non-J&K state villages gap-fill ships | M | LOW | Cat 5 |
| B17 | Sub-panchayat / GP Ward layer | Upstream availability + GP-ward grain citizen indicator | M | LOW | Cat 5 |

**Total**: 17 rows. 0 executable. 17 awaiting trigger.

---

## Known coverage gaps (do NOT re-trigger)

These are documented in [docs/concepts/admin-level-sourcing.md](../docs/concepts/admin-level-sourcing.md) `Known coverage gaps (deferred)` and reflect user-affirmed final dispositions; agents must NOT re-recon them without an explicit upstream change OR user re-scoping:

- **U09 Ladakh villages**: no viable polygon source. Surveyed 2026-05-30. Re-open only if Bhuvan-Ladakh releases OR LGD adds Ladakh coverage AND a village-grain Ladakh indicator surfaces.
- **S03 Assam post-2023 AC polygons**: T4 district fallback is the honest shipped experience. No vector source exists; Furfur Wikimedia SVG is district-shaped not per-AC (probed 2026-05-30). Re-open only if a Tier-1 vector release ships OR Furfur shares the AI source file.

---

## Related active work

- [TODO/20260530-eci-to-lgd-acid-migration-plan.md](20260530-eci-to-lgd-acid-migration-plan.md) — Level-5 successor for `eci_no` -> LGD `AC_ID` corpus migration. R1 audit PENDING; R2+ ESCALATED per CLAUDE.md §6. Independent of this backlog.

---

## See also

- [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md) — 5-gate DoD for when a trigger fires.
- [docs/agents/bootstrap.md](../docs/agents/bootstrap.md) — autonomy stance.
- [CLAUDE.md](../CLAUDE.md) §6 correction levels.

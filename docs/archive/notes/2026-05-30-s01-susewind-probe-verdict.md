# S01 Andhra Pradesh Susewind 2014 probe verdict

**Last Updated**: 2026-05-30

**Source probed**: [Susewind_Assembly_Constituencies_2014.geojsonl.7z](https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/Susewind_Assembly_Constituencies_2014.geojsonl.7z) (CC-BY-SA-NC 4.0, ramSeraph mirror of Susewind R. 2014 Bielefeld University academic release).

**Probe script**: `.tmp_probe_susewind_s01.py` (used `tools.boundaries.snapshot.fetch_geojsonl_7z`).

**Cited by**: [TODO/20260530-boundary-followups-execution-plan.md](../TODO/20260530-boundary-followups-execution-plan.md) Row 5.7.

---

## section 1. Probe findings

| Property | Value |
| --- | --- |
| License | **CC-BY-SA-NC 4.0** (non-commercial; not CC-BY or CC0) |
| Total features | 4,076 |
| First-feature property keys | `ac`, `ac_name`, `pc`, `pc_name`, `state` |
| Andhra Pradesh feature count | **292** |
| Andhra Pradesh first 5 ACs | (pc=1 ac=1) Sirpur / (pc=2 ac=2) Chennur / (pc=2 ac=3) Bellampalli / (pc=2 ac=4) Mancherial / (pc=1 ac=5) Asifabad |

## section 2. Verdict: Path A NOT viable

Susewind 2014 ships **292 features for "Andhra Pradesh"** at **pre-2014-bifurcation unified AP+TG numbering**. The first AC "Sirpur" is in Adilabad PC, which is in **modern Telangana** (TG), not modern AP. This is the SAME structural problem as the existing ramSeraph LGD source.

This reaffirms the finding from [docs/archive/plans/20260529-boundary-rip-and-replace-plan.md](../docs/archive/plans/20260529-boundary-rip-and-replace-plan.md) §C.6 (PR #454): "Susewind 2014 ships 292 features at PRE-bifurcation unified AP+TG numbering ... first AC = 'Sirpur' in Adilabad/TG side".

Even setting aside the structural problem, the **CC-BY-SA-NC** license is a concern for a civic-data project that may have commercial-adjacent downstream consumers. Most other boundary sources in yen-gov are CC0 / CC-BY (commercial-permitted).

## section 3. Remaining paths for Row 5.7

- **Path B (in-repo surgery on existing LGD AP+TG file)** - the only viable structural fix:
  1. Load ramSeraph LGD AC release (294 features for S01 AP+TG).
  2. Filter by `state_lgd == 1` to get the 175 modern-AP features (drop the 119 TG-side residue).
  3. Hand-curate `datasets/reference/in/states/S01/ac_no_remap.json` mapping pre-2014 LGD numbering -> post-2014 ECI numbering via centroid lookup OR name-match.
  4. Replace HTL S01 with the filtered+remapped output.
  5. `verify_ac_parity --state S01` expect >=95%.
  - Effort: 3-4h focused work; risk: hand-curated remap requires careful validation against citizen-visible AC names.

- **Path C (wait for community / new release)** - unbounded; do NOT block on it.

- **Path D (keep HTL S01)** - status quo. HTL ships 177 features (post-2014 AP-only) with ~100% name parity to ECI; this is currently the SHIPPED experience and is structurally correct (just from a different upstream). The "residue cleanup" only matters if we want to drop HTL touchpoints; if HTL is acceptable indefinitely, Row 5.7 closes COLLAPSED.

## section 4. Recommendation

**Path B vs Path D is a user-judgement call**:

- Path B drops HTL touchpoint count 4 -> 3 (S01 leaves HTL; S03 + U07 + U10 remain) but requires hand-curated remap + 3-4h.
- Path D accepts HTL S01 indefinitely (status quo); zero effort; HTL is functional but means yen-gov retains 4 HTL upstream sources rather than 3.

Recommend asking the user: "Is HTL S01 acceptable indefinitely (close Row 5.7 COLLAPSED), or should we invest the 3-4h to drop it (open Path B PR)?"

## section 5. Updates to plan-doc Row 5.7

After this PR merges, Row 5.7 in [TODO/20260530-boundary-followups-execution-plan.md](../TODO/20260530-boundary-followups-execution-plan.md):

- Drop the optimistic Path A-first ordering. Path A is NOT viable (confirmed).
- Reclassify from `PENDING-actionable` to `BLOCKED-on-user-decision` (Path B vs Path D).
- Cite THIS probe verdict.

---

## See also

- [TODO/20260530-boundary-followups-execution-plan.md](../TODO/20260530-boundary-followups-execution-plan.md) - Row 5.7.
- [docs/archive/plans/20260529-boundary-rip-and-replace-plan.md](../docs/archive/plans/20260529-boundary-rip-and-replace-plan.md) §C.6 - prior Susewind finding (PR #454).
- [notes/2026-05-29-ap-assam-ac-source-hunt-handover.md](2026-05-29-ap-assam-ac-source-hunt-handover.md) - HTL S01 current state (177 features post-2014).
